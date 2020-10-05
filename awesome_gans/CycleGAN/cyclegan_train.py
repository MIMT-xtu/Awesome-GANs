from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import tensorflow as tf
import numpy as np

import sys
import time

import cyclegan_model as cyclegan

sys.path.append('../')

import image_utils as iu
from datasets import Pix2PixDataSet as DataSet


results = {
    'output': './gen_img/',
    'model': './model/CycleGAN-model.ckpt'
}

train_step = {
    'epochs': 201,
    'batch_size': 8,
    'logging_step': 100,
}


def main():
    start_time = time.time()  # Clocking start

    # GPU configure
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True

    with tf.Session(config=config) as s:
        # CycleGAN Model
        model = cyclegan.CycleGAN(s,
                                  height=128,
                                  width=128,
                                  channel=3,
                                  batch_size=train_step['batch_size'])

        # Celeb-A DataSet images
        ds = DataSet(height=128,
                     width=128,
                     channel=3,
                     ds_path="D:/DataSet/pix2pix/",
                     ds_name='vangogh2photo')

        img_a = ds.images_a
        img_b = ds.images_b

        print("[*] image A shape : ", img_a.shape)
        print("[*] image B shape : ", img_b.shape)

        n_sample = model.sample_num

        sample_image_height = model.sample_size
        sample_image_width = model.sample_size
        sample_dir_a = results['output'] + 'valid_a.png'
        sample_dir_b = results['output'] + 'valid_b.png'

        sample_a, sample_b = img_a[:n_sample], img_b[:n_sample]
        sample_a = np.reshape(sample_a, [-1] + model.image_shape[1:])
        sample_b = np.reshape(sample_b, [-1] + model.image_shape[1:])

        # Generated image save
        iu.save_images(sample_a, [sample_image_height, sample_image_width], sample_dir_a)
        iu.save_images(sample_b, [sample_image_height, sample_image_width], sample_dir_b)

        print("[+] pre-processing elapsed time : {:.8f}s".format(time.time() - start_time))

        # Initializing
        s.run(tf.global_variables_initializer())

        global_step = 0
        for epoch in range(train_step['epochs']):
            # learning rate decay
            lr_decay = 1.
            if epoch >= 100 and epoch % 10 == 0:
                lr_decay = (train_step['epochs'] - epoch) / (train_step['epochs'] / 2.)

            # re-implement DataIterator for multi-input
            pointer = 0
            num_images = min(ds.n_images_a, ds.n_images_b)
            for i in range(num_images // train_step['batch_size']):
                start = pointer
                pointer += train_step['batch_size']

                if pointer > num_images:  # if ended 1 epoch
                    # Shuffle training DataSet
                    perm_a, perm_b = np.arange(ds.n_images_a), np.arange(ds.n_images_b)

                    np.random.shuffle(perm_a)
                    np.random.shuffle(perm_b)

                    img_a, img_b = img_a[perm_a], img_a[perm_b]

                    start = 0
                    pointer = train_step['batch_size']

                end = pointer

                batch_a = np.reshape(img_a[start:end], model.image_shape)
                batch_b = np.reshape(img_a[start:end], model.image_shape)

                for _ in range(model.n_train_critic):
                    s.run(model.d_op,
                          feed_dict={
                              model.a: batch_a,
                              model.b: batch_b,
                              model.lr_decay: lr_decay,
                          })

                w, gp, g_loss, cycle_loss, _ = s.run([model.w, model.gp, model.g_loss, model.cycle_loss, model.g_op],
                                                     feed_dict={
                                                         model.a: batch_a,
                                                         model.b: batch_b,
                                                         model.lr_decay: lr_decay,
                                                     })

                if global_step % train_step['logging_step'] == 0:
                    # Summary
                    summary = s.run(model.merged,
                                    feed_dict={
                                        model.a: batch_a,
                                        model.b: batch_b,
                                        model.lr_decay: lr_decay,
                                    })

                    # Print loss
                    print("[+] Global Step %08d =>" % global_step,
                          " G loss     : {:.8f}".format(g_loss),
                          " Cycle loss : {:.8f}".format(cycle_loss),
                          " w          : {:.8f}".format(w),
                          " gp         : {:.8f}".format(gp))

                    # Summary saver
                    model.writer.add_summary(summary, global_step=global_step)

                    # Training G model with sample image and noise
                    samples_a2b = s.run(model.g_a2b,
                                        feed_dict={
                                            model.a: sample_a,
                                            model.b: sample_b,
                                            model.lr_decay: lr_decay,
                                        })
                    samples_b2a = s.run(model.g_b2a,
                                        feed_dict={
                                            model.a: sample_a,
                                            model.b: sample_b,
                                            model.lr_decay: lr_decay,
                                        })

                    # Export image generated by model G
                    sample_image_height = model.sample_size
                    sample_image_width = model.sample_size
                    sample_dir_a2b = results['output'] + 'train_a2b_{0}.png'.format(global_step)
                    sample_dir_b2a = results['output'] + 'train_b2a_{0}.png'.format(global_step)

                    # Generated image save
                    iu.save_images(samples_a2b, [sample_image_height, sample_image_width], sample_dir_a2b)
                    iu.save_images(samples_b2a, [sample_image_height, sample_image_width], sample_dir_b2a)

                    # Model save
                    model.saver.save(s, results['model'], global_step=global_step)

                global_step += 1

    end_time = time.time() - start_time  # Clocking end

    # Elapsed time
    print("[+] Elapsed time {:.8f}s".format(end_time))

    # Close tf.Session
    s.close()


if __name__ == '__main__':
    main()
