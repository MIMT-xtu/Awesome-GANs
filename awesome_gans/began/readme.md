# Boundary Equilibrium Generative Adversarial Networks

## Loss Function

* used ```l1 loss```.

## Architecture Networks

* Same with the BEGAN paper.

*DIFFS* | *BEGAN Paper* | *ME*  |
 :---:  |     :---:      | :---: |
 **image size** | ``128`` | ``64`` |
 **skip connection** | ``suggested but not used`` | ``implemented but not used`` |
 
## Tensorboard

![result](./began_tb.png)

> Elapsed time : 8h 18m 32s with ``GTX 1080 8GB x 1``

## Result

*Name* | *Global Step 100k* | *Global Step 200k* | *Global Step 300k*
:---: | :---: | :---: | :---:
**BEGAN**     | ![img](./gen_img/train_100000.png) | ![img](./gen_img/train_200000.png) | ![img](./gen_img/train_300000.png)

## To-Do
* 
