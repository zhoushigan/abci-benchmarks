#!/usr/bin/env python
import argparse
import time

import numpy as np

from chainer import cuda
from chainer import optimizers

import chainer
import cupy

memory_pool = cupy.cuda.MemoryPool(cupy.cuda.memory._mallocManaged)
cupy.cuda.memory.set_allocator(memory_pool.malloc)

parser = argparse.ArgumentParser(
    description=' convnet benchmarks on imagenet')
parser.add_argument('--arch', '-a', default='alexnet',
                    help='Convnet architecture \
                    (alex, googlenet, vgga, overfeat)')
parser.add_argument('--batchsize', '-B', type=int, default=128,
                    help='minibatch size')
parser.add_argument('--gpu', '-g', default=0, type=int,
                    help='GPU ID (negative value indicates CPU)')

args = parser.parse_args()
xp = cuda.cupy if args.gpu >= 0 else np

# Prepare model
print(args.arch)
if args.arch == 'alexnet':
    import alex
    model = alex.Alex()
elif args.arch == 'googlenet':
    import googlenet
    model = googlenet.GoogLeNet()
elif args.arch == 'vgga':
    import vgga
    model = vgga.vgga()
elif args.arch == 'overfeat':
    import overfeat
    model = overfeat.overfeat()
else:
    raise ValueError('Invalid architecture name')

if args.gpu >= 0:
    cuda.get_device(args.gpu).use()
    model.to_gpu()

# Setup optimizer
optimizer = optimizers.SGD(lr=0.01)
optimizer.setup(model)
optimizer.use_cleargrads()


def train_loop():
    # Trainer
    print('model.insize: {}'.format(model.insize))
    print('args.batchsize: {}'.format(args.batchsize), flush=True)
    data = np.ndarray((args.batchsize, 3, model.insize, model.insize), dtype=np.float32)
    data.fill(33333)
    total_forward = 0
    total_backward = 0
    niter = 10

    label = np.ndarray((args.batchsize), dtype=np.int32)
    label.fill(1)
    for i in range(niter):
        print('# Iteration: {}'.format(i))

        x = xp.asarray(data)
        y = xp.asarray(label)

        #optimizer.zero_grads()
        start = xp.cuda.Event()
        end = xp.cuda.Event()
        start.record()
        loss = model(x, y)
        end.record()
        end.synchronize()
        time_ = xp.cuda.get_elapsed_time(start, end)
        if i > 0:
            total_forward += time_
        print('# Forward step time elapsed: {} ms'.format(time_))


        start = xp.cuda.Event()
        end = xp.cuda.Event()
        start.record()
        loss.backward()
        end.record()
        end.synchronize()
        time_ = xp.cuda.get_elapsed_time(start, end)
        if i > 0:
            total_backward += time_
        print('# Backward step time elapsed: {} ms'.format(time_))

        start = xp.cuda.Event()
        end = xp.cuda.Event()
        start.record()
        optimizer.update()
        end.record()
        end.synchronize()
        time_ = xp.cuda.get_elapsed_time(start, end)
        if i > 0:
            total_backward += time_
        print('# Optimizer update time elapsed: {} ms'.format(time_), flush=True)

        del loss

    print('Average Forward:  {} ms'.format((total_forward  / (niter-1))))
    print('Average Backward: {} ms'.format((total_backward / (niter-1))))
    print('Average Total:    {} ms'.format((total_forward + total_backward) / (niter-1)))
    print('')


train_loop()
