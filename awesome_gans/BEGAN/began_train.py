from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import tensorflow as tf
import numpy as np

import sys
import time

import began_model as began

sys.path.append('../')
import image_utils as iu
from datasets import DataIterator
from datasets import CelebADataSet as DataSet


results = {
    'output': './gen_img/',
    'model': './model/BEGAN-model.ckpt'
}

train_step = {
    'epoch': 25,
    'batch_size': 16,
    'logging_step': 1000,
}


def main():
    start_time = time.time()  # Clocking start

    # loading CelebA DataSet
    ds = DataSet(height=64,
                 width=64,
                 channel=3,
                 ds_image_path="/home/zero/hdd/DataSet/CelebA/CelebA-64.h5",
                 ds_label_path="/home/zero/hdd/DataSet/CelebA/Anno/list_attr_celeba.txt",
                 # ds_image_path="/home/zero/hdd/DataSet/CelebA/Img/img_align_celeba/",
                 ds_type="CelebA",
                 use_save=False,
                 save_file_name="/home/zero/hdd/DataSet/CelebA/CelebA-64.h5",
                 save_type="to_h5",
                 use_img_scale=False,
                 # img_scale="-1,1"
                 )

    # saving sample images
    test_images = np.reshape(iu.transform(ds.images[:100], inv_type='127'), (100, 64, 64, 3))
    iu.save_images(test_images,
                   size=[10, 10],
                   image_path=results['output'] + 'sample.png',
                   inv_type='127')

    ds_iter = DataIterator(x=ds.images,
                           y=None,
                           batch_size=train_step['batch_size'],
                           label_off=True)

    # GPU configure
    gpu_config = tf.GPUOptions(allow_growth=True)
    config = tf.ConfigProto(allow_soft_placement=True, gpu_options=gpu_config)

    with tf.Session(config=config) as s:
        # BEGAN Model
        model = began.BEGAN(s, batch_size=train_step['batch_size'], gamma=0.5)  # BEGAN

        # Initializing
        s.run(tf.global_variables_initializer())

        print("[*] Reading checkpoints...")

        saved_global_step = 0
        ckpt = tf.train.get_checkpoint_state('./model/')
        if ckpt and ckpt.model_checkpoint_path:
            # Restores from checkpoint
            model.saver.restore(s, ckpt.model_checkpoint_path)

            saved_global_step = int(ckpt.model_checkpoint_path.split('/')[-1].split('-')[-1])
            print("[+] global step : %d" % saved_global_step, " successfully loaded")
        else:
            print('[-] No checkpoint file found')

        global_step = saved_global_step
        start_epoch = global_step // (ds.num_images // model.batch_size)           # recover n_epoch
        ds_iter.pointer = saved_global_step % (ds.num_images // model.batch_size)  # recover n_iter
        for epoch in range(start_epoch, train_step['epoch']):
            for batch_x in ds_iter.iterate():
                batch_x = iu.transform(batch_x, inv_type='127')
                batch_x = np.reshape(batch_x, (model.batch_size, model.height, model.width, model.channel))
                batch_z = np.random.uniform(-1., 1., [model.batch_size, model.z_dim]).astype(np.float32)

                # Update D network
                _, d_loss = s.run([model.d_op, model.d_loss],
                                  feed_dict={
                                      model.x: batch_x,
                                      model.z: batch_z,
                                  })

                # Update G network
                _, g_loss = s.run([model.g_op, model.g_loss],
                                  feed_dict={
                                      model.z: batch_z,
                                  })

                # Update k_t
                _, k, m_global = s.run([model.k_update, model.k, model.m_global],
                                       feed_dict={
                                            model.x: batch_x,
                                            model.z: batch_z,
                                       })

                if global_step % train_step['logging_step'] == 0:
                    summary = s.run(model.merged,
                                    feed_dict={
                                        model.x: batch_x,
                                        model.z: batch_z,
                                    })

                    # Print loss
                    print("[+] Epoch %03d Step %07d =>" % (epoch, global_step),
                          " D loss : {:.6f}".format(d_loss),
                          " G loss : {:.6f}".format(g_loss),
                          " k : {:.6f}".format(k),
                          " M : {:.6f}".format(m_global))

                    # Summary saver
                    model.writer.add_summary(summary, global_step)

                    # Training G model with sample image and noise
                    sample_z = np.random.uniform(-1., 1., [model.sample_num, model.z_dim]).astype(np.float32)
                    samples = s.run(model.g,
                                    feed_dict={
                                        model.z: sample_z,
                                    })

                    # Export image generated by model G
                    sample_image_height = model.sample_size
                    sample_image_width = model.sample_size
                    sample_dir = results['output'] + 'train_{0}.png'.format(global_step)

                    # Generated image save
                    iu.save_images(samples,
                                   size=[sample_image_height, sample_image_width],
                                   image_path=sample_dir,
                                   inv_type='127')

                    # Model save
                    model.saver.save(s, results['model'], global_step=global_step)

                # Learning Rate update
                if global_step and global_step % model.lr_update_step == 0:
                    s.run([model.g_lr_update, model.d_lr_update])

                global_step += 1

    end_time = time.time() - start_time  # Clocking end

    # Elapsed time
    print("[+] Elapsed time {:.8f}s".format(end_time))

    # Close tf.Session
    s.close()


if __name__ == '__main__':
    main()
