import tensorflow as tf
from PIL import Image
import cv2
import numpy as np


def edge(img):
    img = np.array(img)
    blurred = cv2.GaussianBlur(img, (3, 3), 0)

    gray = cv2.cvtColor(blurred, cv2.COLOR_RGB2GRAY)

    xgrad = cv2.Sobel(gray, cv2.CV_16SC1, 1, 0)
    ygrad = cv2.Sobel(gray, cv2.CV_16SC1, 0, 1)

    edge_output = cv2.Canny(xgrad, ygrad, 50, 150)

    dst = cv2.bitwise_and(img, img, mask=edge_output)
    return dst


def lrelu(x, trainbable=None):
    alpha = 0.2
    return tf.maximum(alpha * x, x)


def prelu(x, trainable=True):
    alpha = tf.compat.v1.get_variable(
        name='alpha',
        shape=x.get_shape()[-1],
        dtype=tf.float32,
        initializer=tf.compat.v1.constant_initializer(0.0),
        trainable=trainable)
    return tf.maximum(0.0, x) + alpha * tf.minimum(0.0, x)


def conv_layer(x, filter_shape, stride, trainable=True):
    filter_ = tf.compat.v1.get_variable(
        name='weight',
        shape=filter_shape,
        dtype=tf.float32,
        initializer=tf.compat.v1.keras.initializers.VarianceScaling(scale=1.0, mode="fan_avg", distribution="uniform"),
        trainable=trainable)
    return tf.nn.conv2d(
        input=x,
        filters=filter_,
        strides=[1, stride, stride, 1],
        padding='SAME')


def deconv_layer(x, filter_shape, output_shape, stride, trainable=True):
    filter_ = tf.compat.v1.get_variable(
        name='weight',
        shape=filter_shape,
        dtype=tf.float32,
        initializer=tf.compat.v1.keras.initializers.VarianceScaling(scale=1.0, mode="fan_avg", distribution="uniform"),
        trainable=trainable)
    return tf.nn.conv2d_transpose(
        input=x,
        filters=filter_,
        output_shape=output_shape,
        strides=[1, stride, stride, 1])


def max_pooling_layer(x, size, stride):
    return tf.nn.max_pool2d(
        input=x,
        ksize=[1, size, size, 1],
        strides=[1, stride, stride, 1],
        padding='SAME')


def avg_pooling_layer(x, size, stride):
    return tf.nn.avg_pool2d(
        input=x,
        ksize=[1, size, size, 1],
        strides=[1, stride, stride, 1],
        padding='SAME')


def full_connection_layer(x, out_dim, trainable=True):
    in_dim = x.get_shape().as_list()[-1]
    W = tf.compat.v1.get_variable(
        name='weight',
        shape=[in_dim, out_dim],
        dtype=tf.float32,
        initializer=tf.compat.v1.truncated_normal_initializer(stddev=0.1),
        trainable=trainable)
    b = tf.compat.v1.get_variable(
        name='bias',
        shape=[out_dim],
        dtype=tf.float32,
        initializer=tf.compat.v1.constant_initializer(0.0),
        trainable=trainable)
    return tf.add(tf.matmul(x, W), b)


def batch_normalize(x, is_training, decay=0.99, epsilon=0.001, trainable=True):
    def bn_train():
        batch_mean, batch_var = tf.nn.moments(x=x, axes=[0, 1, 2])
        train_mean = tf.compat.v1.assign(
            pop_mean, pop_mean * decay + batch_mean * (1 - decay))
        train_var = tf.compat.v1.assign(
            pop_var, pop_var * decay + batch_var * (1 - decay))
        with tf.control_dependencies([train_mean, train_var]):
            return tf.nn.batch_normalization(
                x, batch_mean, batch_var, beta, scale, epsilon)

    def bn_inference():
        return tf.nn.batch_normalization(
            x, pop_mean, pop_var, beta, scale, epsilon)

    dim = x.get_shape().as_list()[-1]
    beta = tf.compat.v1.get_variable(
        name='beta',
        shape=[dim],
        dtype=tf.float32,
        initializer=tf.compat.v1.truncated_normal_initializer(stddev=0.0),
        trainable=trainable)
    scale = tf.compat.v1.get_variable(
        name='scale',
        shape=[dim],
        dtype=tf.float32,
        initializer=tf.compat.v1.truncated_normal_initializer(stddev=0.1),
        trainable=trainable)
    pop_mean = tf.compat.v1.get_variable(
        name='pop_mean',
        shape=[dim],
        dtype=tf.float32,
        initializer=tf.compat.v1.constant_initializer(0.0),
        trainable=False)
    pop_var = tf.compat.v1.get_variable(
        name='pop_var',
        shape=[dim],
        dtype=tf.float32,
        initializer=tf.compat.v1.constant_initializer(1.0),
        trainable=False)
    return tf.cond(pred=is_training, true_fn=bn_train, false_fn=bn_inference)


def gkern(kernlen=13, nsig=1.6):
    import scipy.ndimage.filters as fi
    # create nxn zeros
    inp = np.zeros((kernlen, kernlen))
    # set element at the middle to one, a dirac delta
    inp[kernlen // 2, kernlen // 2] = 1
    # gaussian-smooth the dirac, resulting in a gaussian filter mask
    return fi.gaussian_filter(inp, nsig)


def flatten_layer(x):
    input_shape = x.get_shape().as_list()
    dim = input_shape[1] * input_shape[2] * input_shape[3]
    transposed = tf.transpose(a=x, perm=(0, 3, 1, 2))
    return tf.reshape(transposed, [-1, dim])


def pixel_shuffle_layerg(x, r, n_split):
    def PS(x, r):
        bs, a, b, c = x.get_shape().as_list()
        if bs == 1:
            x = tf.reshape(x, (a, b, r, r))
            x = tf.transpose(a=x, perm=(0, 1, 3, 2))
            # print(x.shape)
            x = tf.split(x, a, 0)
            x = tf.concat([tf.squeeze(x_) for x_ in x], 1)
            # x = tf.expand_dims(x, 0)
            x = tf.split(x, b, 0)
            # x = tf.concat([tf.squeeze(x_) for x_ in x], 2)
            x = tf.concat([tf.squeeze(x_) for x_ in x], 1)
            # x = tf.concat([tf.squeeze(x_) for x_ in x], 2)
        else:
            x = tf.reshape(x, (bs, a, b, r, r))
            x = tf.transpose(a=x, perm=(0, 1, 2, 4, 3))
            # print(x.shape)
            x = tf.split(x, a, 1)
            x = tf.concat([tf.squeeze(x_) for x_ in x], 2)
            # x = tf.expand_dims(x, 0)
            x = tf.split(x, b, 1)
            # x = tf.concat([tf.squeeze(x_) for x_ in x], 2)
            x = tf.concat([tf.squeeze(x_) for x_ in x], 2)
            # x = tf.concat([tf.squeeze(x_) for x_ in x], 2)
        return tf.reshape(x, (bs, a * r, b * r, 1))

    xc = tf.split(x, n_split, 3)
    return tf.concat([PS(x_, r) for x_ in xc], 3)


def pixel_shuffle_layer(x, r, n_split):
    def PS(x, r):
        bs, a, b, c = x.get_shape().as_list()
        x = tf.reshape(x, (bs, a, b, r, r))
        x = tf.transpose(a=x, perm=(0, 1, 2, 4, 3))
        x = tf.split(x, a, 1)
        x = tf.concat([tf.squeeze(x_) for x_ in x], 2)
        x = tf.split(x, b, 1)
        x = tf.concat([tf.squeeze(x_) for x_ in x], 2)
        return tf.reshape(x, (bs, a * r, b * r, 1))

    xc = tf.split(x, n_split, 3)
    return tf.concat([PS(x_, r) for x_ in xc], 3)


def _PS(X, r, n_out_channel):
    if n_out_channel >= 1:
        assert int(X.get_shape()[-1]) == (r ** 2) * n_out_channel, _err_log
        bsize, a, b, c = X.get_shape().as_list()
        bsize = tf.shape(input=X)[0]  # Handling Dimension(None) type for undefined batch dim
        # X = tf.cast(X, tf.int32)
        Xs = tf.split(X, r, 3)  # b*h*w*r*r dtype
        # Xs = tf.split(X, r, 3)
        Xr = tf.concat(Xs, 2)  # b*h*(r*w)*r
        X = tf.reshape(Xr, (bsize, r * a, r * b, n_out_channel))  # b*(r*h)*(r*w)*c
    else:
        print(_err_log)
    return X


def PS_layer(X, r, n_split):
    if n_split >= 1:
        assert int(X.get_shape()[-1]) == (r ** 2) * n_split, _err_log

        # x0 = []
        def PS(x, r):
            bsize, a, b, c = x.get_shape().as_list()
            # bs, a, b, c = x.get_shape().as_list()
            bsize = tf.shape(input=x)[0]
            x = tf.reshape(x, (bsize, a, b, r, r))
            # x = tf.transpose(x, (0, 1, 2, 4, 3))
            # print(x.shape)
            x = tf.split(x, a, 1)
            x = tf.concat([tf.squeeze(x) for x_ in x], 3)
            x = tf.split(x, b, 2)
            x = tf.concat([tf.squeeze(x) for x_ in x], 4)
            x = tf.reshape(x, (bsize, a * r, b * r, 1))
            return x

        xc = tf.split(X, n_split, 3)
        x0 = tf.concat([PS(x, r) for x in xc], 3)
    else:
        print(_err_log)
    return x0

    # xc = tf.split(x, n_split, 3)
    # return tf.concat([PS(x_, r) for x_ in xc], 3)


def down_sample(X):
    bs, a, b, c = X.get_shape().as_list()
    b = (int)(b)
    a = (int)(a)
    c = (int)(c)
    OFF = 1
    scale = 4
    # img0 = tf.Variable(tf.zeros([bs, a, b, c]))
    img1 = tf.slice(X, [0, 0, 0, 0], [bs, a, b - OFF, c])
    img11 = tf.slice(X, [0, 0, 0, 0], [bs, a, OFF, c])
    image1 = tf.concat([img1, img11], 2)
    # image1 = tf.concat([img11,img1],2)
    img2 = tf.slice(X, [0, 0, 0, 0], [bs, a - OFF, b, c])
    img22 = tf.slice(X, [0, 0, 0, 0], [bs, OFF, b, c])
    image2 = tf.concat([img2, img22], 1)
    # image2 = tf.concat([img22,img2],1)
    img3 = tf.slice(X, [0, 0, OFF, 0], [bs, a, b - OFF, c])
    img33 = tf.slice(X, [0, 0, b - OFF, 0], [bs, a, OFF, c])
    image3 = tf.concat([img3, img33], 2)
    img4 = tf.slice(X, [0, OFF, 0, 0], [bs, a - OFF, b, c])
    img44 = tf.slice(X, [0, a - OFF, 0, 0], [bs, OFF, b, c])
    image4 = tf.concat([img4, img44], 1)

    '''def offset(img, x, y=None):
        x = (int)(x)
        if y is None:
            y = x
        else:
            y = (int)(y)
        if x < 0:
            for i in range(img.shape[1] + x):
                img0[:, i-x, :, :] = img[:, i, :, :]
            for i in range(-x):
                img0[:, i, :, :] = img[:, i, :, :]
        else:
            for i in range(img.shape[1] - x):
                img0[:, i, :, :] = img[:, i + x, :, :]
            for i in range(img.shape[1] - x, img.shape[1], 1):
                img0[:, i, :, :] = img[:, i, :, :]

        if y < 0:
            for i in range(img.shape[2] + y):
                img0[:, :, i-y, :] = img[:, :, i: :]
            for i in range(-y):
                img0[:, :, i, :] = img[:, :, i: :]
        else:
            for i in range(img.shape[2] - y):
                img0[:, :, i, :] = img[:, :, i + y, :]
            for i in range(img.shape[2] - y, img.shape[2], 1):
                img0[:, :, i, :] = img[:, :, i, :]

        return img0'''

    # img1 = offset(X, (OFF), (0))
    # image1 = image1.resize((bs, a//scale, b//scale, c), interpolation=cv2.INTER_CUBIC)
    image1 = tf.image.resize(image1, [a // scale, b // scale], method=1)
    # img2 = offset(X, (-OFF), (0))
    image2 = tf.image.resize(image2, [a // scale, b // scale], method=1)
    # image2 = cv2.resize(image2, (bs, a//scale, b//scale, c), interpolation=cv2.INTER_CUBIC)
    # img3 = offset(X, (0), (OFF))
    image3 = tf.image.resize(image3, [a // scale, b // scale], method=1)
    # image3 = cv2.resize(image3, (bs, a//scale, b//scale, c), interpolation=cv2.INTER_CUBIC)
    # img4 = offset(X, (0), (-OFF))
    image4 = tf.image.resize(image4, [a // scale, b // scale], method=1)
    # image4 = cv2.resize(image4, (bs, a//scale, b//scale, c), interpolation=cv2.INTER_CUBIC)
    image5 = tf.image.resize(X, [a // scale, b // scale], method=1)
    # image5 = cv2.resize(X, (bs, a//scale, b//scale, c), interpolation=cv2.INTER_CUBIC)
    image = tf.concat([image1, image2, image3, image4, image5], 3)
    return image


def pool_sample(X):
    bs, a, b, c = X.get_shape().as_list()
    b = (int)(b)
    a = (int)(a)
    c = (int)(c)
    OFF = 1
    scale = 4
    # img0 = tf.Variable(tf.zeros([bs, a, b, c]))
    img1 = tf.slice(X, [0, 0, 0, 0], [bs, a, b - OFF, c])
    img11 = tf.slice(X, [0, 0, 0, 0], [bs, a, OFF, c])
    image1 = tf.concat([img1, img11], 2)
    img2 = tf.slice(X, [0, 0, 0, 0], [bs, a - OFF, b, c])
    img22 = tf.slice(X, [0, 0, 0, 0], [bs, OFF, b, c])
    image2 = tf.concat([img2, img22], 1)
    img3 = tf.slice(X, [0, 0, OFF, 0], [bs, a, b - OFF, c])
    img33 = tf.slice(X, [0, 0, b - OFF, 0], [bs, a, OFF, c])
    image3 = tf.concat([img3, img33], 2)
    img4 = tf.slice(X, [0, OFF, 0, 0], [bs, a - OFF, b, c])
    img44 = tf.slice(X, [0, a - OFF, 0, 0], [bs, OFF, b, c])
    image4 = tf.concat([img4, img44], 1)
    scale = 4
    image1 = avg_pooling_layer(image1, 2,
                               2)  # tf.nn.avg_pool(image1, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')
    image2 = avg_pooling_layer(image2, 2,
                               2)  # tf.nn.avg_pool(image2, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')
    image3 = avg_pooling_layer(image3, 2,
                               2)  # tf.nn.avg_pool(image3, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')
    image4 = avg_pooling_layer(image4, 2,
                               2)  # tf.nn.avg_pool(image4, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')
    image5 = avg_pooling_layer(X, 2, 2)  # tf.nn.avg_pool(X, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')
    image = tf.concat([image1, image2, image3, image4, image5], 3)
    return image


def Feature_enhance(x1, x2, x3, x4, n):
    bs, a, b, c = x1.get_shape().as_list()
    # 1,2
    x1_1 = tf.slice(x1, [0, a - n, 0, 0], [bs, n, b, c])
    x1_2 = tf.slice(x1, [0, 0, 0, 0], [bs, a - n, b, c])
    x2_1 = tf.slice(x2, [0, 0, 0, 0], [bs, n, b, c])
    x2_2 = tf.slice(x2, [0, n, 0, 0], [bs, a - n, b, c])
    x12_1 = x1_1 * 0.5 + x2_1 * 0.5
    x12 = tf.concat([x1_2, x12_1, x2_2], 1)
    # 3,4
    x3_1 = tf.slice(x3, [0, a - n, 0, 0], [bs, n, b, c])
    x3_2 = tf.slice(x3, [0, 0, 0, 0], [bs, a - n, b, c])
    x4_1 = tf.slice(x4, [0, 0, 0, 0], [bs, n, b, c])
    x4_2 = tf.slice(x4, [0, n, 0, 0], [bs, a - n, b, c])
    x34_1 = x3_1 * 0.5 + x4_1 * 0.5
    x34 = tf.concat([x3_2, x34_1, x4_2], 1)
    # 1,2,3,4
    x12_2 = tf.slice(x12, [0, 0, b - n, 0], [bs, a * 2 - n, n, c])
    x12_3 = tf.slice(x12, [0, 0, 0, 0], [bs, a * 2 - n, b - n, c])
    x34_2 = tf.slice(x34, [0, 0, 0, 0], [bs, a * 2 - n, n, c])
    x34_3 = tf.slice(x34, [0, 0, n, 0], [bs, a * 2 - n, b - n, c])
    x1234_1 = x12_2 * 0.5 + x34_2 * 0.5
    x1234 = tf.concat([x12_3, x1234_1, x34_3], 2)

    return x1234
