import math
import tensorflow as tf
import numpy as np
import dnnlib.tflib as tflib
from functools import partial
import misc
import PIL
from PIL import Image
import os 

def create_stub(name, batch_size):
    return tf.constant(0, dtype='float32', shape=(batch_size, 0))


def create_latentvariable_for_generator(name, batch_size=1):
    return tf.get_variable('learnable_dlatents',
            shape=(batch_size, 512),
            dtype='float32',
            initializer=tf.initializers.random_normal())

def create_labelvariable_for_generator(name, batch_size=1):
    return tf.get_variable('learnable_dlabels',
            shape=(batch_size, 60),
            dtype='float32',
            initializer=tf.initializers.random_normal())
        


class Generator:
    def __init__(self, model, labels_size=60, batch_size=1, clipping_threshold=1, model_res=128):
        self.batch_size = batch_size
        self.clipping_threshold=clipping_threshold
        # self.tiled_dlatent=tiled_dlatent
        # self.model_scale = int(2*(math.log(model_res,2)-1)) # For example, 1024 -> 18
        self.initial_dlatents = misc.random_latents(1, model, random_state=np.random.RandomState(800)) #np.zeros((self.batch_size, 512))
        self.initial_dlabels = np.random.rand(self.batch_size, labels_size)

        # image = Gs.run(latents, labels, minibatch_size=1, num_gpus=1, out_mul=127.5, out_add=127.5, out_shrink=1, out_dtype=np.uint8)

        # model.get_output_for(self.initial_dlatents, self.initial_dlabels, minibatch_size=self.batch_size, out_dtype=np.uint8,
        # custom_inputs=[partial(create_latentvariable_for_generator, batch_size=batch_size),
        # partial(create_labelvariable_for_generator, batch_size=batch_size)])

        # self.dlatent_avg_def = model.get_var('dlatent_avg')
        # self.reset_dlatent_avg()
        self.sess = tf.get_default_session()
        self.graph = tf.get_default_graph()

        # self.sess.run()

        # self.dlatent_variable = next(v for v in tf.global_variables() if 'learnable_dlatents' in v.name)
        # self.dlabel_variable = next(v for v in tf.global_variables() if 'learnable_dlabels' in v.name)
        def get_tensor(name):
            try:
                return self.graph.get_tensor_by_name(name)
            except KeyError:
                return None


        self.dlatent_variable = tf.get_variable('learnable_dlatents',
            shape=(batch_size, 512),
            dtype='float32',
            initializer=tf.initializers.random_normal())

        self.dlabel_variable = tf.get_variable('learnable_dlabels',
            shape=(batch_size, 60),
            dtype='float32',
            initializer=tf.initializers.random_normal())

        
        self.generator_output = model.get_output_for(self.dlatent_variable, self.dlabel_variable)

        # self.dlatent_variable = get_tensor(latents_name)

        # self.dlabel_variable = get_tensor(labels_name)
        self.latents_name_tensor = get_tensor(model.input_templates[0].name)
        self.labels_name_tensor = get_tensor(model.input_templates[1].name)
        self.output_name_tensor = get_tensor(model.output_templates[0].name)

        self.output_name_image= tflib.convert_images_to_uint8(self.output_name_tensor, nchw_to_nhwc=True, uint8_cast=False)
        self.output_name_image_uint8 = tf.saturate_cast(self.output_name_image, tf.uint8)
        

        self.set_dlatents(self.initial_dlatents)
        self.set_dlabels(self.initial_dlabels)

        
        

        # self.generator_latents_input = get_tensor(latents_name)
        # self.generator_labels_input = get_tensor(labels_name)
        # self.generator_output = get_tensor(output_name)
        self.generator_output_shape=model.output_shape

        # if self.generator_latents_input is None or self.generator_labels_input is None or self.generator_output is None:
        #     for op in self.graph.get_operations():
        #         print(op)
        #     raise Exception("Couldn't find "+latents_name+" or "+labels_name+" or "+output_name)

        if self.generator_output is None:
            for op in self.graph.get_operations():
                print(op)
            raise Exception("Couldn't find generator_output")

        self.generated_image = tflib.convert_images_to_uint8(self.generator_output, nchw_to_nhwc=True, uint8_cast=False)
        self.generated_image_uint8 = tf.saturate_cast(self.generated_image, tf.uint8)

        # Implement stochastic clipping similar to what is described in https://arxiv.org/abs/1702.04782
        # (Slightly different in that the latent space is normal gaussian here and was uniform in [-1, 1] in that paper,
        # so we clip any vector components outside of [-2, 2]. It seems fine, but I haven't done an ablation check.)
        clipping_mask1 = tf.math.logical_or(self.dlatent_variable > self.clipping_threshold, self.dlatent_variable < -self.clipping_threshold)
        clipped_values1 = tf.where(clipping_mask1, tf.random_normal(shape=(self.batch_size, 512)), self.dlatent_variable)
        self.stochastic_clip_op1 = tf.assign(self.dlatent_variable, clipped_values1)

        clipping_mask2 = tf.math.logical_or(self.dlabel_variable > self.clipping_threshold, self.dlabel_variable < 0)
        clipped_values2 = tf.where(clipping_mask2, tf.random_normal(shape=(self.batch_size, 60)), self.dlabel_variable)
        self.stochastic_clip_op2 = tf.assign(self.dlabel_variable, clipped_values2)

        # self.sess.run([self.dlatent_variable, self.dlabel_variable], 
        # feed_dict={self.dlatent_variable.name: clipped_values1, self.dlabel_variable.name: clipped_values2})

    def reset_dlatents(self):
        self.set_dlatents(self.initial_dlatents)
    
    def reset_dlabels(self):
        self.set_dlabels(self.initial_dlabels)

    def set_dlatents(self, dlatents):
        # if (dlatents.shape != (self.batch_size, 512)):
        #     dlatents = np.vstack([dlatents, np.zeros((self.batch_size-dlatents.shape[0], 512))])
        # assert (dlatents.shape == (self.batch_size, 512))
        self.sess.run(tf.assign(self.dlatent_variable, dlatents))
        # self.sess.run(self.dlatent_variable, feed_dict={self.dlatent_variable.name:dlatents})
    
    def set_dlabels(self, dlabels):
        # if (dlabels.shape != (self.batch_size, 60)):
        #     dlabels = np.vstack([dlabels, np.zeros((self.batch_size-dlabels.shape[0], 60))])
        # assert (dlabels.shape == (self.batch_size, 60))
        self.sess.run(tf.assign(self.dlabel_variable, dlabels))
        # self.sess.run(self.dlabel_variable, feed_dict={self.dlabel_variable.name:dlabels})

    def stochastic_clip_dvariables(self):
        # clipping_mask1 = tf.math.logical_or(self.dlatent_variable > self.clipping_threshold, self.dlatent_variable < -self.clipping_threshold)
        # clipped_values1 = tf.where(clipping_mask1, tf.random_normal(shape=(self.batch_size, 512)), self.dlatent_variable)
        # # self.stochastic_clip_op1 = tf.assign(self.dlatent_variable, clipped_values1)

        # clipping_mask2 = tf.math.logical_or(self.dlabel_variable > self.clipping_threshold, self.dlabel_variable < -self.clipping_threshold)
        # clipped_values2 = tf.where(clipping_mask2, tf.random_normal(shape=(self.batch_size, 60)), self.dlabel_variable)
        # # self.stochastic_clip_op2 = tf.assign(self.dlabel_variable, clipped_values2)

        # self.sess.run([self.dlatent_variable, self.dlabel_variable], 
        # feed_dict={self.dlatent_variable.name: clipped_values1, self.dlabel_variable.name: clipped_values2})

        self.sess.run([self.stochastic_clip_op1, self.stochastic_clip_op2])

    def get_dvariables(self):
        return self.sess.run([self.dlatent_variable, self.dlabel_variable])

    def generate_images(self, dlatents=None):
        if dlatents:
            self.set_dlatents(dlatents)
        return self.sess.run(self.generated_image_uint8)
    
    def get_beautify_image(self, dlatents=None,dlabels=None, index=None,dir=None):
        # self.latents_name_tensor = get_tensor(model.input_templates[0].name)
        # self.labels_name_tensor = get_tensor(model.input_templates[1].name)
        # self.output_name_tensor = get_tensor(model.output_templates[0].name)
        # self.output_name_tensor
        for k in range(10):
            y_pred = dlabels[:]
            y_pred = y_pred + (k*0.05)
            y_pred = np.clip(y_pred, 0.0, 1.0)
            img=self.sess.run(self.output_name_image_uint8, feed_dict={self.labels_name_tensor: y_pred, self.latents_name_tensor: dlatents})
            img = PIL.Image.fromarray(img[0], 'RGB')
            img.save(os.path.join(dir, '{}-{}.png'.format('%04d' % index,k)), 'PNG')
    
    def get_generate_image_shape(self):
        return self.generator_output_shape
