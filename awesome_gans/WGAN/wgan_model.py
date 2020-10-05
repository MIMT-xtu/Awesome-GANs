import tensorflow as tf

import sys

sys.path.append('../')
import tfutil as t


tf.set_random_seed(777)


class WGAN:

    def __init__(self, s, batch_size=32, height=32, width=32, channel=3, n_classes=10,
                 sample_num=8 * 8, sample_size=8,
                 z_dim=128, gf_dim=64, df_dim=64, fc_unit=512,
                 enable_gp=True):

        """
        # General Settings
        :param s: TF Session
        :param batch_size: training batch size, default 32
        :param height: input image height, default 32
        :param width: input image width, default 32
        :param channel: input image channel, default 3
        :param n_classes: input DataSet's classes

        # Output Settings
        :param sample_num: the number of output images, default 64
        :param sample_size: sample image size, default 8

        # Training Option
        :param z_dim: z dimension (kinda noise), default 128
        :param gf_dim: the number of generator filters, default 64
        :param df_dim: the number of discriminator filters, default 64
        :param fc_unit: the number of fc units, default 512
        :param enable_gp: enabling gradient penalty, default True
        """

        self.s = s
        self.batch_size = batch_size
        self.height = height
        self.width = width
        self.channel = channel
        self.n_classes = n_classes

        self.sample_size = sample_size
        self.sample_num = sample_num

        self.image_shape = [self.height, self.width, self.channel]

        self.z_dim = z_dim
        self.gf_dim = gf_dim
        self.df_dim = df_dim
        self.fc_unit = fc_unit

        # Training Options - based on the WGAN paper
        self.beta1 = 0.  # 0.5
        self.beta2 = .9  # 0.999
        self.lr = 1e-4
        self.critic = 5
        self.clip = .01
        self.d_clip = []  # (-0.01 ~ 0.01)
        self.d_lambda = 10.
        self.decay = .9

        self.EnableGP = enable_gp

        # pre-defined
        self.d_loss = 0.
        self.g_loss = 0.
        self.gradient_penalty = 0.

        self.g = None

        self.d_op = None
        self.g_op = None

        self.merged = None
        self.writer = None
        self.saver = None

        # Placeholders
        self.x = tf.placeholder(tf.float32, shape=[None, self.height, self.width, self.channel],
                                name='x-images')
        self.z = tf.placeholder(tf.float32, shape=[None, self.z_dim],
                                name='z-noise')

        self.build_wgan()  # build WGAN model

    """ResNet like model for Cifar-10 DataSet
    def mean_pool_conv(self, x, f, reuse=None, name=""):
        with tf.variable_scope(name, reuse=reuse):
            x = tf.add_n([x[:, ::2, ::2, :], x[:, 1::2, ::2, :], x[:, ::2, 1::2, :], x[:, 1::2, 1::2, :]]) / 4.
            x = t.conv2d(x, f, 3, 1)
            return x

    def conv_mean_pool(self, x, f, reuse=None, name=""):
        with tf.variable_scope(name, reuse=reuse):
            x = t.conv2d(x, f, 3, 1)
            x = tf.add_n([x[:, ::2, ::2, :], x[:, 1::2, ::2, :], x[:, ::2, 1::2, :], x[:, 1::2, 1::2, :]]) / 4.
            return x

    def upsample_conv(self, x, f, reuse=None, name=""):
        with tf.variable_scope(name, reuse=reuse):
            x = tf.concat([x, x, x, x], axis=-1)
            x = tf.depth_to_space(x, 2)
            x = t.conv2d(x, f, 3, 1)
            return x

    def residual_block(self, x, f, sampling=None, reuse=None, name=""):
        with tf.variable_scope(name, reuse=reuse):
            shortcut = tf.identity(x, name=(name + "-" + sampling + "-identity"))

            is_gen = name.startswith('gen')

            if is_gen:
                x = t.batch_norm(x, name='%s-bn-1' % (name + "-" + sampling))
            x = tf.nn.relu(x)

            if sampling == 'up':
                x = self.upsample_conv(x, f, reuse, name + "-" + sampling + "-upsample_conv-1")
            elif sampling == 'down' or sampling == 'none':
                x = t.conv2d(x, f, name='%s-conv2d-1' % (name + "-" + sampling))

            if is_gen:
                x = t.batch_norm(x, name='%s-bn-2' % (name + "-" + sampling))
            x = tf.nn.relu(x)

            if sampling == 'up' or sampling == 'none':
                x = t.conv2d(x, f, name='%s-conv2d-2' % (name + "-" + sampling))
            elif sampling == 'down':
                x = self.conv_mean_pool(x, f, reuse, name + "-" + sampling + "-conv_mean_pool-1")

            if sampling == 'up':
                shortcut = self.upsample_conv(shortcut, f, reuse, name + "-" + sampling + "-upsample_conv-2")
            elif sampling == 'down':
                shortcut = self.conv_mean_pool(shortcut, f, reuse, name + "-" + sampling + "-conv_mean_pool-2")

            return shortcut + x

    def residual_block_init(self, x, f, reuse=None, name=""):
        with tf.variable_scope(name, reuse=reuse):
            shortcut = tf.identity(x)

            x = t.conv2d(x, f, 1, name='rb_init-conv2d-1')
            x = tf.nn.relu(x)

            x = self.conv_mean_pool(x, f, reuse=reuse, name='rb_init-conv_mean_pool-1')
            shortcut = self.mean_pool_conv(shortcut, 1, reuse=reuse, name='rb_init-mean_pool_conv-1')

            return shortcut + x

    def discriminator(self, x, reuse=None):
        with tf.variable_scope('discriminator', reuse=reuse):
            x = self.residual_block_init(x, self.z_dim, reuse=reuse, name='disc-res_block_init')

            x = self.residual_block(x, self.z_dim, reuse=reuse, sampling='down', name='disc-res_block-1')
            x = self.residual_block(x, self.z_dim, reuse=reuse, sampling='none', name='disc-res_block-2')
            x = self.residual_block(x, self.z_dim, reuse=reuse, sampling='none', name='disc-res_block-3')

            x = tf.nn.relu(x)

            x = t.global_avg_pooling(x)

            x = t.dense(x, 1, name='disc-fc-1')
            return x

    def generator(self, z, reuse=None):
        with tf.variable_scope('generator', reuse=reuse):
            x = t.dense(z, self.z_dim * 4 * 4, name="gen-fc-1")
            x = tf.reshape(x, [-1, 4, 4, self.z_dim])

            for i in range(1, 4):
                x = self.residual_block(x, self.z_dim, sampling='up', name='gen-res_block-%d' % i)

            x = t.batch_norm(x, name='gen-bn-1')
            x = tf.nn.relu(x)

            x = t.conv2d(x, 3, 3, 1, name="gen-conv2d-1")
            x = tf.nn.tanh(x)
            return x
    """

    def generator(self, z, reuse=None):
        with tf.variable_scope('generator', reuse=reuse):
            x = t.dense(z, self.gf_dim * 4 * 4 * 4, name='gen-fc-1')
            x = t.batch_norm(x, reuse=reuse, name='gen-bn-1')
            x = tf.nn.relu(x)

            x = tf.reshape(x, (-1, 4, 4, self.gf_dim * 4))

            for i in range(1, 4):
                x = t.deconv2d(x, self.gf_dim * 4 // (2 ** (i - 1)), 5, 2, name='gen-deconv2d-%d' % i)
                x = t.batch_norm(x, reuse=reuse, name='gen-bn-%d' % (i + 1))
                x = tf.nn.relu(x)

            x = t.deconv2d(x, self.channel, 5, 1, name='gen-deconv2d-5')
            x = tf.nn.tanh(x)
            return x

    def discriminator(self, x, reuse=None):
        with tf.variable_scope('discriminator', reuse=reuse):
            x = tf.reshape(x, (-1, self.height, self.width, self.channel))

            x = t.conv2d(x, self.df_dim, 5, 2, name='disc-conv2d-1')
            x = tf.nn.leaky_relu(x)

            for i in range(1, 3):
                x = t.conv2d(x, self.df_dim, 5, 2, name='disc-conv2d-%d' % (i + 1))
                x = t.batch_norm(x, reuse=reuse, name='disc-bn-%d' % i)
                x = tf.nn.leaky_relu(x)

            x = t.flatten(x)

            x = t.dense(x, 1, name='disc-fc-1')
            return x

    def build_wgan(self):
        # Generator
        self.g = self.generator(self.z)

        # Discriminator
        d_real = self.discriminator(self.x)
        d_fake = self.discriminator(self.g, reuse=True)

        # Losses
        d_real_loss = t.sce_loss(d_real, tf.ones_like(d_real))
        d_fake_loss = t.sce_loss(d_fake, tf.zeros_like(d_fake))
        self.d_loss = d_real_loss + d_fake_loss
        self.g_loss = t.sce_loss(d_fake, tf.ones_like(d_fake))

        # The gradient penalty loss
        if self.EnableGP:
            alpha = tf.random_uniform(shape=[self.batch_size, 1, 1, 1], minval=0., maxval=1., name='alpha')
            diff = self.g - self.x  # fake data - real data
            interpolates = self.x + alpha * diff
            d_interp = self.discriminator(interpolates, reuse=True)
            gradients = tf.gradients(d_interp, [interpolates])[0]
            slopes = tf.sqrt(tf.reduce_sum(tf.square(gradients), reduction_indices=[1]))
            self.gradient_penalty = tf.reduce_mean(tf.square(slopes - 1.))

            # Update D loss
            self.d_loss += self.d_lambda * self.gradient_penalty

        # Summary
        tf.summary.scalar("loss/d_real_loss", d_real_loss)
        tf.summary.scalar("loss/d_fake_loss", d_fake_loss)
        tf.summary.scalar("loss/d_loss", self.d_loss)
        tf.summary.scalar("loss/g_loss", self.g_loss)
        if self.EnableGP:
            tf.summary.scalar("misc/gp", self.gradient_penalty)

        # Collect trainer values
        t_vars = tf.trainable_variables()
        d_params = [v for v in t_vars if v.name.startswith('discriminator')]
        g_params = [v for v in t_vars if v.name.startswith('generator')]

        if not self.EnableGP:
            self.d_clip = [v.assign(tf.clip_by_value(v, -self.clip, self.clip)) for v in d_params]

        # Optimizer
        if self.EnableGP:
            self.d_op = tf.train.AdamOptimizer(learning_rate=self.lr * 2,
                                               beta1=self.beta1, beta2=self.beta2).minimize(loss=self.d_loss,
                                                                                            var_list=d_params)
            self.g_op = tf.train.AdamOptimizer(learning_rate=self.lr * 2,
                                               beta1=self.beta1, beta2=self.beta2).minimize(loss=self.g_loss,
                                                                                            var_list=g_params)
        else:
            self.d_op = tf.train.RMSPropOptimizer(learning_rate=self.lr,
                                                  decay=self.decay).minimize(self.d_loss, var_list=d_params)
            self.g_op = tf.train.RMSPropOptimizer(learning_rate=self.lr,
                                                  decay=self.decay).minimize(self.g_loss, var_list=g_params)

        # Merge summary
        self.merged = tf.summary.merge_all()

        # Model Saver
        self.saver = tf.train.Saver(max_to_keep=1)
        self.writer = tf.summary.FileWriter('./model/', self.s.graph)
