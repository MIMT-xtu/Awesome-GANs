from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import tensorflow as tf
import numpy as np

import sys
import time

import srgan_model as srgan

sys.path.append('../')
import image_utils as iu
from datasets import Div2KDataSet as DataSet


np.random.seed(1337)


results = {
    'output': './gen_img/',
    'model': './model/SRGAN-model.ckpt'
}

train_step = {
    'batch_size': 16,
    'init_epochs': 100,
    'train_epochs': 1501,
    'global_step': 200001,
    'logging_interval': 100,
}


def main():
    start_time = time.time()  # Clocking start

    # Div2K - Track 1: Bicubic downscaling - x4 DataSet load
    """
    ds = DataSet(ds_path="/home/zero/hdd/DataSet/DIV2K/",
                 ds_name="X4",
                 use_save=True,
                 save_type="to_h5",
                 save_file_name="/home/zero/hdd/DataSet/DIV2K/DIV2K",
                 use_img_scale=True)
    """
    ds = DataSet(ds_hr_path="/home/zero/hdd/DataSet/DIV2K/DIV2K-hr.h5",
                 ds_lr_path="/home/zero/hdd/DataSet/DIV2K/DIV2K-lr.h5",
                 use_img_scale=True)

    hr, lr = ds.hr_images, ds.lr_images

    print("[+] Loaded HR image ", hr.shape)
    print("[+] Loaded LR image ", lr.shape)

    # GPU configure
    gpu_config = tf.GPUOptions(allow_growth=True)
    config = tf.ConfigProto(allow_soft_placement=True, log_device_placement=False, gpu_options=gpu_config)

    with tf.Session(config=config) as s:
        with tf.device("/gpu:1"):  # Change
            # SRGAN Model
            model = srgan.SRGAN(s, batch_size=train_step['batch_size'],
                                use_vgg19=False)

        # Initializing
        s.run(tf.global_variables_initializer())

        # Load model & Graph & Weights
        ckpt = tf.train.get_checkpoint_state('./model/')
        if ckpt and ckpt.model_checkpoint_path:
            # Restores from checkpoint
            model.saver.restore(s, ckpt.model_checkpoint_path)

            global_step = int(ckpt.model_checkpoint_path.split('/')[-1].split('-')[-1])
            print("[+] global step : %d" % global_step, " successfully loaded")
        else:
            global_step = 0
            print('[-] No checkpoint file found')

        start_epoch = global_step // (ds.n_images // train_step['batch_size'])

        rnd = np.random.randint(0, ds.n_images)
        sample_x_hr, sample_x_lr = hr[rnd], lr[rnd]

        sample_x_hr, sample_x_lr = \
            np.reshape(sample_x_hr, [1] + model.hr_image_shape[1:]), \
            np.reshape(sample_x_lr, [1] + model.lr_image_shape[1:])

        # Export real image
        # valid_image_height = model.sample_size
        # valid_image_width = model.sample_size
        sample_hr_dir, sample_lr_dir = results['output'] + 'valid_hr.png', results['output'] + 'valid_lr.png'

        # Generated image save
        iu.save_images(sample_x_hr,
                       size=[1, 1],
                       image_path=sample_hr_dir,
                       inv_type='127')

        iu.save_images(sample_x_lr,
                       size=[1, 1],
                       image_path=sample_lr_dir,
                       inv_type='127')

        learning_rate = 1e-4
        for epoch in range(start_epoch, train_step['train_epochs']):
            pointer = 0
            for i in range(ds.n_images // train_step['batch_size']):
                start = pointer
                pointer += train_step['batch_size']

                if pointer > ds.n_images:  # if 1 epoch is ended
                    # Shuffle training DataSet
                    perm = np.arange(ds.n_images)
                    np.random.shuffle(perm)

                    hr, lr = hr[perm], lr[perm]

                    start = 0
                    pointer = train_step['batch_size']

                end = pointer

                batch_x_hr, batch_x_lr = hr[start:end], lr[start:end]

                # reshape
                batch_x_hr = np.reshape(batch_x_hr, [train_step['batch_size']] + model.hr_image_shape[1:])
                batch_x_lr = np.reshape(batch_x_lr, [train_step['batch_size']] + model.lr_image_shape[1:])

                # Update Only G network
                d_loss, g_loss, g_init_loss = 0., 0., 0.
                if epoch <= train_step['init_epochs']:
                    _, g_init_loss = s.run([model.g_init_op, model.g_cnt_loss],
                                           feed_dict={
                                               model.x_hr: batch_x_hr,
                                               model.x_lr: batch_x_lr,
                                               model.lr: learning_rate,
                                           })
                # Update G/D network
                else:
                    _, d_loss = s.run([model.d_op, model.d_loss],
                                      feed_dict={
                                          model.x_hr: batch_x_hr,
                                          model.x_lr: batch_x_lr,
                                          model.lr: learning_rate,
                                      })

                    _, g_loss = s.run([model.g_op, model.g_loss],
                                      feed_dict={
                                          model.x_hr: batch_x_hr,
                                          model.x_lr: batch_x_lr,
                                          model.lr: learning_rate,
                                      })

                if i % train_step['logging_interval'] == 0:
                    # Print loss
                    if epoch <= train_step['init_epochs']:
                        print("[+] Epoch %04d Step %08d => " % (epoch, global_step),
                              " MSE loss : {:.8f}".format(g_init_loss))
                    else:
                        print("[+] Epoch %04d Step %08d => " % (epoch, global_step),
                              " D loss : {:.8f}".format(d_loss),
                              " G loss : {:.8f}".format(g_loss))

                        summary = s.run(model.merged,
                                        feed_dict={
                                            model.x_hr: batch_x_hr,
                                            model.x_lr: batch_x_lr,
                                            model.lr: learning_rate,
                                        })

                        # Summary saver
                        model.writer.add_summary(summary, global_step)

                    # Training G model with sample image and noise
                    sample_x_lr = np.reshape(sample_x_lr, [model.sample_num] + model.lr_image_shape[1:])
                    samples = s.run(model.g,
                                    feed_dict={
                                        model.x_lr: sample_x_lr,
                                        model.lr: learning_rate,
                                    })

                    # Export image generated by model G
                    # sample_image_height = model.output_height
                    # sample_image_width = model.output_width
                    sample_dir = results['output'] + 'train_{:08d}.png'.format(global_step)

                    # Generated image save
                    iu.save_images(samples,
                                   size=[1, 1],
                                   image_path=sample_dir,
                                   inv_type='127')

                    # Model save
                    model.saver.save(s, results['model'], global_step)

                # Learning Rate update
                if epoch and epoch % model.lr_update_epoch == 0:
                    learning_rate *= model.lr_decay_rate
                    learning_rate = max(learning_rate, model.lr_low_boundary)

                global_step += 1

    end_time = time.time() - start_time  # Clocking end

    # Elapsed time
    print("[+] Elapsed time {:.8f}s".format(end_time))

    # Close tf.Session
    s.close()


if __name__ == '__main__':
    main()
