from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import tensorflow as tf
import numpy as np

import sys
import time

import lapgan_model as lapgan

sys.path.append('../')
import image_utils as iu
from datasets import DataIterator
from datasets import CiFarDataSet as DataSet


np.random.seed(1337)


results = {
    'output': './gen_img/',
    'model': './model/LAPGAN-model.ckpt'
}

train_step = {
    'epoch': 200,
    'batch_size': 64,
    'logging_interval': 1000,
}


def main():
    start_time = time.time()  # Clocking start

    # Training, test data set
    ds = DataSet(height=32,
                 width=32,
                 channel=3,
                 ds_path='D:\\DataSet/cifar/cifar-10-batches-py/',
                 ds_name='cifar-10')

    ds_iter = DataIterator(ds.train_images, ds.train_labels,
                           train_step['batch_size'])

    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True

    with tf.Session(config=config) as s:
        # LAPGAN model
        model = lapgan.LAPGAN(s, batch_size=train_step['batch_size'])

        # Initializing variables
        s.run(tf.global_variables_initializer())

        # Load model & Graph & Weights
        saved_global_step = 0
        ckpt = tf.train.get_checkpoint_state('./model/')
        if ckpt and ckpt.model_checkpoint_path:
            model.saver.restore(s, ckpt.model_checkpoint_path)

            saved_global_step = int(ckpt.model_checkpoint_path.split('/')[-1].split('-')[-1])
            print("[+] global step : %s" % saved_global_step, " successfully loaded")
        else:
            print('[-] No checkpoint file found')

        sample_y = np.zeros(shape=[model.sample_num, model.n_classes])
        for i in range(10):
            sample_y[10 * i:10 * (i + 1), i] = 1

        global_step = saved_global_step
        start_epoch = global_step // (len(ds.train_images) // model.batch_size)  # recover n_epoch
        ds_iter.pointer = saved_global_step % (len(ds.train_images) // model.batch_size)  # recover n_iter
        for epoch in range(start_epoch, train_step['epoch']):
            for batch_images, batch_labels in ds_iter.iterate():
                batch_x = iu.transform(batch_images, inv_type='127')

                z = []
                for i in range(3):
                    z.append(np.random.uniform(-1., 1., [train_step['batch_size'], model.z_noises[i]]))

                # Update D/G networks
                img_fake, img_coarse, d_loss_1, g_loss_1, \
                _, _, _, d_loss_2, g_loss_2, \
                _, _, d_loss_3, g_loss_3, \
                _, _, _, _, _, _ = s.run([
                    model.g[0], model.x1_coarse, model.d_loss[0], model.g_loss[0],

                    model.x2_fine, model.g[1], model.x2_coarse, model.d_loss[1], model.g_loss[1],

                    model.x3_fine, model.g[2], model.d_loss[2], model.g_loss[2],

                    model.d_op[0], model.g_op[0], model.d_op[1], model.g_op[1], model.d_op[2], model.g_op[2],
                ],
                    feed_dict={
                        model.x1_fine: batch_x,  # images
                        model.y: batch_labels,   # classes
                        model.z[0]: z[0], model.z[1]: z[1], model.z[2]: z[2],  # z-noises
                        model.do_rate: 0.5,
                    })

                # Logging
                if global_step % train_step['logging_interval'] == 0:
                    batch_x = ds.test_images[np.random.randint(0, len(ds.test_images), model.sample_num)]
                    batch_x = iu.transform(batch_x, inv_type='127')

                    z = []
                    for i in range(3):
                        z.append(np.random.uniform(-1., 1., [model.sample_num, model.z_noises[i]]))

                    # Update D/G networks
                    img_fake, img_coarse, d_loss_1, g_loss_1, \
                    _, _, _, d_loss_2, g_loss_2, \
                    _, _, d_loss_3, g_loss_3, \
                    _, _, _, _, _, _, summary = s.run([
                        model.g[0], model.x1_coarse, model.d_loss[0], model.g_loss[0],

                        model.x2_fine, model.g[1], model.x2_coarse, model.d_loss[1], model.g_loss[1],

                        model.x3_fine, model.g[2], model.d_loss[2], model.g_loss[2],

                        model.d_op[0], model.g_op[0], model.d_op[1], model.g_op[1], model.d_op[2], model.g_op[2],

                        model.merged,
                    ],
                        feed_dict={
                            model.x1_fine: batch_x,  # images
                            model.y: sample_y,       # classes
                            model.z[0]: z[0], model.z[1]: z[1], model.z[2]: z[2],  # z-noises
                            model.do_rate: 0.,
                        })

                    # Print loss
                    d_loss = (d_loss_1 + d_loss_2 + d_loss_3) / 3.
                    g_loss = (g_loss_1 + g_loss_2 + g_loss_3) / 3.
                    print("[+] Epoch %03d Step %05d => " % (epoch, global_step),
                          " Avg D loss : {:.8f}".format(d_loss),
                          " Avg G loss : {:.8f}".format(g_loss))

                    # Training G model with sample image and noise
                    samples = img_fake + img_coarse

                    # Summary saver
                    model.writer.add_summary(summary, global_step)  # time saving

                    # Export image generated by model G
                    sample_image_height = model.sample_size
                    sample_image_width = model.sample_size
                    sample_dir = results['output'] + 'train_{0}.png'.format(global_step)

                    # Generated image save
                    iu.save_images(samples, size=[sample_image_height, sample_image_width],
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
