from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import tensorflow as tf
import numpy as np

import os
import sys
import time

import anogan_model as anogan

sys.path.append('../')
import image_utils as iu
from datasets import DataIterator
from datasets import CelebADataSet as DataSet


results = {
    'output': './gen_img/',
    'orig-model': './orig-model/AnoGAN-model.ckpt',
    'ano-model': './ano-model/AnoGAN-model.ckpt'
}

train_step = {
    'epoch': 100,
    'batch_size': 64,
    'logging_step': 2000,
}


def main():
    start_time = time.time()  # Clocking start

    # GPU configure
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True

    with tf.Session(config=config) as s:
        if os.path.exists("./orig-model/"):
            detect = True  # There has to be pre-trained file
        else:
            detect = False

        # AnoGAN Model
        model = anogan.AnoGAN(detect=detect,
                              use_label=False)  # AnoGAN

        # Initializing
        s.run(tf.global_variables_initializer())

        # loading CelebA DataSet
        ds = DataSet(height=64,
                     width=64,
                     channel=3,
                     ds_image_path="D:\\DataSet/CelebA/CelebA-64.h5",
                     ds_label_path="D:\\DataSet/CelebA/Anno/list_attr_celeba.txt",
                     # ds_image_path="D:\\DataSet/CelebA/Img/img_align_celeba/",
                     ds_type="CelebA",
                     use_save=False,
                     save_file_name="D:\\DataSet/CelebA/CelebA-128.h5",
                     save_type="to_h5",
                     use_img_scale=False,
                     # img_scale="-1,1"
                     )

        # saving sample images
        test_images = np.reshape(iu.transform(ds.images[:16], inv_type='127'), (16, 64, 64, 3))
        iu.save_images(test_images,
                       size=[4, 4],
                       image_path=results['output'] + 'sample.png',
                       inv_type='127')

        ds_iter = DataIterator(x=ds.images,
                               y=None,
                               batch_size=train_step['batch_size'],
                               label_off=True)

        # To-Do
        # Getting anomaly data

        # Load model & Graph & Weights
        if not detect or not os.path.exists("./ano-model/"):
            ckpt = tf.train.get_checkpoint_state('./orig-model/')
        else:
            ckpt = tf.train.get_checkpoint_state('./ano-model/')

        saved_global_step = 0
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
            for batch_images in ds_iter.iterate():
                batch_x = np.reshape(batch_images, [-1] + model.image_shape[1:])
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

                if global_step % train_step['logging_step'] == 0:
                    batch_z = np.random.uniform(-1., 1., [model.batch_size, model.z_dim]).astype(np.float32)

                    # Summary
                    d_loss, g_loss, summary = s.run([model.d_loss, model.g_loss, model.merged],
                                                    feed_dict={
                                                        model.x: batch_x,
                                                        model.z: batch_z,
                                                    })

                    # Print loss
                    print("[+] Epoch %04d Step %07d =>" % (epoch, global_step),
                          " D loss : {:.8f}".format(d_loss),
                          " G loss : {:.8f}".format(g_loss))

                    # Summary saver
                    model.writer.add_summary(summary, epoch)

                    # Training G model with sample image and noise
                    sample_z = np.random.uniform(-1., 1., [model.sample_num, model.z_dim]).astype(np.float32)
                    samples = s.run(model.g_test,
                                    feed_dict={
                                        model.z: sample_z,
                                    })

                    # Export image generated by model G
                    sample_image_height = model.sample_size
                    sample_image_width = model.sample_size
                    sample_dir = results['output'] + 'train_{0}_{1}.png'.format(epoch, global_step)

                    # Generated image save
                    iu.save_images(samples,
                                   size=[sample_image_height, sample_image_width],
                                   image_path=sample_dir)

                    # Model save
                    if not detect:
                        model.saver.save(s, results['orig-model'], global_step=global_step)
                    else:
                        model.saver.save(s, results['ano-model'], global_step=global_step)

                global_step += 1

    end_time = time.time() - start_time  # Clocking end

    # Elapsed time
    print("[+] Elapsed time {:.8f}s".format(end_time))

    # Close tf.Session
    s.close()


if __name__ == '__main__':
    main()
