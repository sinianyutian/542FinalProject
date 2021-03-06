import tensorflow as tf
from networks.network import Network


#define

n_classes = 81
_feat_stride = [16,]
anchor_scales = [8, 16, 32]

class VGGnet_train(Network):
    def __init__(self, trainable=True):
        self.inputs = []
        self.data = tf.placeholder(tf.float32, shape=[None, None, None, 4])
        self.im_info = tf.placeholder(tf.float32, shape=[None, 3])
        self.gt_boxes = tf.placeholder(tf.float32, shape=[None, 5])
        self.gt_masks = tf.placeholder(tf.float32, shape=[None, None, None])
        self.keep_prob = tf.placeholder(tf.float32)
        self.layers = dict({'data':self.data, 'im_info':self.im_info, 'gt_boxes':self.gt_boxes, 'gt_masks':self.gt_masks})
        self.trainable = trainable
        self.setup()

        # create ops and placeholders for bbox normalization process
        with tf.variable_scope('bbox_pred', reuse=True):
            weights = tf.get_variable("weights")
            biases = tf.get_variable("biases")

            self.bbox_weights = tf.placeholder(weights.dtype, shape=weights.get_shape())
            self.bbox_biases = tf.placeholder(biases.dtype, shape=biases.get_shape())

            self.bbox_weights_assign = weights.assign(self.bbox_weights)
            self.bbox_bias_assign = biases.assign(self.bbox_biases)

    def setup(self):
        (self.feed('data')
             .conv(3, 3, 64, 1, 1, name='conv1_1')
             .conv(3, 3, 64, 1, 1, name='conv1_2', )
             .max_pool(2, 2, 2, 2, padding='VALID', name='pool1')
             .conv(3, 3, 128, 1, 1, name='conv2_1', )
             .conv(3, 3, 128, 1, 1, name='conv2_2', )
             .max_pool(2, 2, 2, 2, padding='VALID', name='pool2')
             .conv(3, 3, 256, 1, 1, name='conv3_1', )
             .conv(3, 3, 256, 1, 1, name='conv3_2', )
             .conv(3, 3, 256, 1, 1, name='conv3_3', )
             .max_pool(2, 2, 2, 2, padding='VALID', name='pool3')
             .conv(3, 3, 512, 1, 1, name='conv4_1', )
             .conv(3, 3, 512, 1, 1, name='conv4_2', )
             .conv(3, 3, 512, 1, 1, name='conv4_3', )
             .max_pool(2, 2, 2, 2, padding='VALID', name='pool4')
             .conv(3, 3, 512, 1, 1, name='conv5_1', )
             .conv(3, 3, 512, 1, 1, name='conv5_2', )
             .conv(3, 3, 512, 1, 1, name='conv5_3', ))
        #========= RPN ============
        (self.feed('conv5_3')
             .conv(3,3,512,1,1,name='rpn_conv/3x3')
             .conv(1,1,len(anchor_scales)*3*2 ,1 , 1, padding='VALID', relu = False, name='rpn_cls_score'))

        (self.feed('rpn_cls_score','gt_boxes','im_info','data')
             .anchor_target_layer(_feat_stride, anchor_scales, name = 'rpn-data' ))

        (self.feed('rpn_conv/3x3')
             .conv(1,1,len(anchor_scales)*3*4, 1, 1, padding='VALID', relu = False, name='rpn_bbox_pred'))

        #========= RoI Proposal ============
        (self.feed('rpn_cls_score')   
             .reshape_layer(2,name = 'rpn_cls_score_reshape')  # output shape: 1*(9H)*W*2
             .softmax(name='rpn_cls_prob'))   # keep the shape

        (self.feed('rpn_cls_prob')
             .reshape_layer(len(anchor_scales)*3*2,name = 'rpn_cls_prob_reshape')) # output shape: 1*H*W*18

        (self.feed('rpn_cls_prob_reshape','rpn_bbox_pred','im_info')
             .proposal_layer(_feat_stride, anchor_scales, 'TRAIN',name = 'rpn_rois'))

        (self.feed('rpn_rois','gt_boxes','gt_masks')
             .proposal_target_layer(n_classes,name = 'roi-data'))


        #========= RCNN ============
        (self.feed('conv5_3', 'roi-data')
             .roi_pool(7, 7, 1.0/16, name='pool_5')
             .conv(3, 3, 1024, 1, 1, name='conv6_1')
             .conv(3, 3, 1024, 1, 1, name='conv6_2')
             .conv(3, 3, 1024, 1, 1, name='conv6_3')
             .fc(1024, name='fc6')
	         .dropout(0.5, name='drop6')
             .fc(1024, name='fc7')
	         .dropout(0.5, name='drop7')
             .fc(n_classes, relu=False, name='cls_score')
             .sigmoid(name='cls_prob'))

        (self.feed('drop7')
             .fc(n_classes*4, relu=False, name='bbox_pred'))

        # New branch for segmentation mask
        (self.feed('conv6_3')
             .upscore(2, 2, 256, name='up_1')
             .conv(1, 1, n_classes, 1, 1, name='mask_out')
             .sigmoid(name='mask_prob'))
