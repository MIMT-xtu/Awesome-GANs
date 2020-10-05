from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import tensorflow as tf
import numpy as np

import sys
import time

import acgan_model as acgan

sys.path.append('../')
import image_utils as iu
from datasets import DataIterator
from datasets import CiFarDataSet as DataSet


results = {
    'output': './gen_img/',
    'model': './model/ACGAN-model.ckpt'
}

train_step = {
    'epochs': 101,
    'batch_size': 100,
    'global_step': 50001,
    'logging_interval': 500,
}


def main():
    start_time = time.time()  # Clocking start

    # Loading Cifar-10 DataSet
    ds = DataSet(height=32,
                 width=32,
                 channel=3,
                 ds_path="D:/DataSet/cifar/cifar-10-batches-py/",
                 ds_name='cifar-10')

    ds_iter = DataIterator(x=iu.transform(ds.train_images, '127'),
                           y=ds.train_labels,
                           batch_size=train_step['batch_size'],
                           label_off=False)  # using label # maybe someday, i'll change this param's name

    # Generated image save
    test_images = iu.transform(ds.test_images[:100], inv_type='127')
    iu.save_images(test_images,
                   size=[10, 10],
                   image_path=results['output'] + 'sample.png',
                   inv_type='127')

    # GPU configure
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True

    with tf.Session(config=config) as s:
        # ACGAN Model
        model = acgan.ACGAN(s,
                            batch_size=train_step['batch_size'],
                            n_classes=ds.n_classes)

        # Initializing
        s.run(tf.global_variables_initializer())

        sample_y = np.zeros(shape=[model.sample_num, model.n_classes])
        for i in range(10):
            sample_y[10 * i:10 * (i + 1), i] = 1

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
        start_epoch = global_step // (len(ds.train_images) // model.batch_size)           # recover n_epoch
        ds_iter.pointer = saved_global_step % (len(ds.train_images) // model.batch_size)  # recover n_iter
        for epoch in range(start_epoch, train_step['epochs']):
            for batch_x, batch_y in ds_iter.iterate():
                batch_z = np.random.uniform(-1., 1., [model.batch_size, model.z_dim]).astype(np.float32)

                # Update D network
                _, d_loss = s.run([model.d_op, model.d_loss],
                                  feed_dict={
                                      model.x: batch_x,
                                      model.y: batch_y,
                                      model.z: batch_z,
                                  })

                # Update G/C networks
                _, g_loss, _, c_loss = s.run([model.g_op, model.g_loss, model.c_op, model.c_loss],
                                             feed_dict={
                                                 model.x: batch_x,
                                                 model.y: batch_y,
                                                 model.z: batch_z,
                                             })

                if global_step % train_step['logging_interval'] == 0:
                    batch_z = np.random.uniform(-1., 1., [model.batch_size, model.z_dim]).astype(np.float32)

                    d_loss, g_loss, c_loss, summary = s.run([model.d_loss, model.g_loss, model.c_loss, model.merged],
                                                            feed_dict={
                                                                model.x: batch_x,
                                                                model.y: batch_y,
                                                                model.z: batch_z,
                                                            })

                    # Print loss
                    print("[+] Epoch %04d Step %08d => " % (epoch, global_step),
                          " D loss : {:.8f}".format(d_loss),
                          " G loss : {:.8f}".format(g_loss),
                          " C loss : {:.8f}".format(c_loss))

                    # Training G model with sample image and noise
                    sample_z = np.random.uniform(-1., 1., [model.sample_num, model.z_dim]).astype(np.float32)
                    samples = s.run(model.g,
                                    feed_dict={
                                        model.y: sample_y,
                                        model.z: sample_z,
                                    })

                    # Summary saver
                    model.writer.add_summary(summary, global_step)

                    # Export image generated by model G
                    sample_image_height = model.sample_size
                    sample_image_width = model.sample_size
                    sample_dir = results['output'] + 'train_{:08d}.png'.format(global_step)

                    # Generated image save
                    iu.save_images(samples,
                                   size=[sample_image_height, sample_image_width],
                                   image_path=sample_dir,
                                   inv_type='127')

                    # Model save
                    model.saver.save(s, results['model'], global_step)

                global_step += 1

    end_time = time.time() - start_time  # Clocking end

    # Elapsed time
    print("[+] Elapsed time {:.8f}s".format(end_time))

    # Close tf.Session
    s.close()


if __name__ == '__main__':
    main()
