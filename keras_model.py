import keras
import numpy as np
import tensorflow as tf
from keras import backend as K
from keras import Model
from keras.activations import relu
from keras.layers import LSTM, Activation, Dense, Embedding, Input
from keras.optimizers import Adam
from keras.callbacks import ModelCheckpoint, ReduceLROnPlateau

print("Tensorflow version", tf.__version__)
print("Keras version", keras.__version__)


class OurModel():

    def __init__(self, sentences, target_labels, args):
        """
        args:
            sentences: list of strings
            true_labels: list of true labels (True/False array)
        """
        self.data_len = len(target_labels)
        self.sentences = tf.constant(sentences)
        self.target_labels = tf.constant(target_labels)
        self.args = args

        # Preprocess the input strings.
        hash_buckets = 10_000
        words = tf.strings.split(sentences, ' ')
        self.hashed_words = tf.strings.to_hash_bucket_fast(words, hash_buckets)

        # Build the Keras model.
        inpt = Input(shape=[None], dtype=tf.int64, ragged=True)
        x = Embedding(hash_buckets, 16)(inpt)
        x = LSTM(32, use_bias=False)(x)
        x = Dense(32)(x)
        x = Activation(relu)(x)
        x = Dense(1)(x)

        self.model = Model(inpt, x)
        
        self.model.compile(
            loss='binary_crossentropy', 
            optimizer=Adam(0.001)
        )

        self.model.summary()

    def run(self, confidence=0.3):
        """
        the range (confidence, 1-confidence) will be treated as "uncertain results"
        """
        # manual validation split
        split = round(self.data_len * 0.3)
        x = self.hashed_words[-split:]
        y = self.target_labels[-split:]
        valx = self.hashed_words[:-split]
        valy = self.target_labels[:-split]

        # callbacks
        callbacks = [
            ModelCheckpoint("models/test.hdf5", verbose=1, save_best_only=True, save_freq="epoch"),
            ReduceLROnPlateau(patience=self.args.epochs//5)
        ]

        # fitting
        try:
            self.model.fit(
                x=x,
                y=y,
                validation_data=(valx,valy),
                epochs=self.args.epochs,
                batch_size=self.args.batchsize,
                validation_batch_size=self.args.batchsize,
                verbose=1,
                callbacks=callbacks,
            )
        except KeyboardInterrupt:
            print("\nManual early stop...")

        # evaluating
        def calc_correct(inputs, targets, name):
            predicts = np.squeeze(self.model.predict(inputs))
            targets = K.eval(targets)

            correct_neg = 1 - targets[predicts < confidence]
            correct_pos = targets[predicts > (1-confidence)]
            correct = np.sum(correct_pos) + np.sum(correct_neg)
            uncertain = np.sum(
                np.logical_and(
                    (predicts >= confidence),
                    (predicts <= (1-confidence))
                )
            )
            print("\n" + name.title())
            print(correct, "correct out of", len(targets))
            print(correct/len(targets))
            print(uncertain, "uncertain")

        calc_correct(x, y, name="training set")
        calc_correct(valx, valy, name="validation set")
        calc_correct(self.hashed_words, self.target_labels, name="combined")


