import os
import sys
import torch
import logging
from datetime import datetime

os.environ['HTTP_PROXY'] = 'http://proxy:3128/'
os.environ['HTTPS_PROXY'] = 'http://proxy:3128/'
# os.environ["CUDA_VISIBLE_DEVICES"] = "7"

torch.set_num_threads(1)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.getcwd()))))
print(ROOT_DIR)
sys.path.insert(1, ROOT_DIR + "/")
sys.path.insert(0, ROOT_DIR + "/")

from Code.Semi_supervised.Train.Model_M0.M0_main import M0_Pipeline
from Code.Semi_supervised.Train.Model_M1.M1_main import M1_Pipeline
from Code.Semi_supervised.Test.main import Test_Pipeline


class Pipeline:
    def __init__(self, dataset_path, modelWeights_path, log_path, dataset_type, isUnified, device):
        self.dataset_type = dataset_type

        if self.dataset_type == "chaos":
            self.isChaos = True
        else:
            self.isChaos = False
            self.dataset_type = "clinical"

        # Model Weights
        if isUnified:
            self.train_type = "Unified"
            self.temp_model_train_type = self.dataset_type + "_" + self.train_type
        else:
            self.train_type = "Frozen"
            self.temp_model_train_type = self.dataset_type + "_" + self.train_type
        self.modelWeights_path = modelWeights_path
        self.M0_model_path = self.modelWeights_path + "M0_" + self.temp_model_train_type + ".pth"
        self.M0_bw_path = self.modelWeights_path + "M0_bw_" + self.temp_model_train_type + ".pth"

        self.M1_model_path = self.modelWeights_path + "M1_" + self.temp_model_train_type + ".pth"
        self.M1_bw_path = self.modelWeights_path + "M1_bw_" + self.temp_model_train_type + ".pth"

        self.csv_file = "dataset.csv"
        self.dataset_path = dataset_path
        self.logPath = log_path + "runs/" + self.temp_model_train_type

        self.device = device

        self.isUnified = isUnified

        self.log_date = datetime.now().strftime("%Y.%m.%d")
        self.log_file_path = self.logPath + "_{}".format(self.log_date)+ "_log.txt"

        logging.basicConfig(filename=self.log_file_path, filemode='w', level=logging.DEBUG)
        logging.getLogger('matplotlib.font_manager').disabled = True

    def getModelM0(self):
        obj = M0_Pipeline(self.dataset_path, self.M0_model_path, self.M0_bw_path, self.logPath)
        modelM0 = obj.defineModel()
        modelM0.load_state_dict(torch.load(self.M0_model_path))
        modelM0.to(self.device)
        return modelM0

    def trainModel_M0(self, epochs, logger):
        obj = M0_Pipeline(self.dataset_path, self.M0_model_path, self.M0_bw_path,self.device, self.logPath,
                          epochs=epochs)
        obj.trainModel(logger)

    def trainModel_M1(self, model_M0, epochs, logger, M0_model_path=None, M0_bw_path=None):
        obj_M1 = M1_Pipeline(self.dataset_path, self.M1_model_path, self.M1_bw_path, self.device, self.logPath,
                             self.isChaos, self.isUnified, epochs)
        train_loader, validation_loader, test_loader = obj_M1.train_val_test_slit()
        dataloaders = [train_loader, validation_loader]
        log_path = obj_M1.trainModel(model_M0, dataloaders, logger, M0_model_path, M0_bw_path)

        if self.dataset_type == "chaos":
            obj_Test = Test_Pipeline(self.M0_model_path,self.M0_bw_path,self.M1_model_path,self.M1_bw_path,
                                     self.dataset_path,self.logPath,self.device)
            obj_Test.testModel(test_loader, log_path)
