import copy
import time
import os
from datetime import datetime
import matplotlib.pyplot as plt

import torch

torch.set_num_threads(1)
from skimage.filters import threshold_otsu
from sklearn.metrics import f1_score
from torch.cuda.amp import autocast, GradScaler
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm

from Code.Utils.loss import DiceLoss
scaler = GradScaler()


def saveImage(img, lbl, op):
    # create grid of images
    figure = plt.figure(figsize=(10, 10))
    plt.subplot(131, title="MRI")
    plt.grid(False)
    plt.imshow(img.permute(1, 2, 0), cmap="gray")
    plt.subplot(132, title="GT")
    plt.grid(False)
    plt.imshow(lbl.permute(1, 2, 0), cmap="gray")
    plt.subplot(133, title="OP")
    plt.grid(False)
    plt.imshow(op.permute(1, 2, 0).to(torch.float), cmap="gray")

    return figure


def train(dataloaders, modelPath, modelPath_bestweight, num_epochs, model, optimizer,
          log=False, device="cuda:3"):
    if log:
        start_time = datetime.now().strftime("%Y.%m.%d.%H.%M.%S")
        TBLOGDIR = "/project/mukhopad/tmp/LiverTumorSeg/Code/Semi-supervised/student/runs/Training/Teacher_Unet3D/{}".format(
            start_time)
        writer = SummaryWriter(TBLOGDIR)
    best_model_wts = ""
    best_acc = 0.0
    best_val_loss = 99999
    since = time.time()
    # model.to(device)
    criterion = DiceLoss()
    store_idx = int(len(dataloaders[0])/2)
    # criterion = torch.nn.
    for epoch in range(num_epochs):
        print('Epoch {}/{}'.format(epoch, num_epochs))
        print('-' * 10)
        # Each epoch has a training and validation phase
        for phase in [0, 1]:
            if phase == 0:
                print("Model In Training mode")
                model.train()  # Set model to training mode
            else:
                print("Model In Validation mode")
                model.eval()  # Set model to evaluate mode

            running_loss = 0.0
            running_corrects = 0
            idx = 0
            # Iterate over data.
            for batch in tqdm(dataloaders[phase]):
                image_batch, labels_batch = batch

                optimizer.zero_grad()
                # forward
                with torch.set_grad_enabled(phase == 0):
                    with autocast(enabled=True):
                        outputs = model(image_batch.unsqueeze(1))
                        loss, acc = criterion(outputs[0].squeeze(1), labels_batch.to(device))

                    # backward + optimize only if in training phase
                    if phase == 0:
                        scaler.scale(loss).backward()
                        scaler.step(optimizer)
                        scaler.update()

                        if epoch % 5 == 0 and idx == store_idx:
                            print("Storing images", idx, epoch)
                            img = image_batch[:1, 14:15, :, :].squeeze(0).detach().cpu()
                            lbl = labels_batch[:1, 14:15, :, :].squeeze(0).detach().cpu()
                            op = outputs[0][:1, :1, 14:15, :, :].squeeze(0).squeeze(0).detach().cpu()

                            fig = saveImage(img, lbl, op)
                            text = "Images"
                            writer.add_figure(text, fig, epoch)

                    # statistics
                    running_loss += loss.item()
                    """outputs = outputs[0].cpu().detach().numpy() >= threshold_otsu(outputs[0].cpu().detach().numpy())
                    running_corrects += f1_score(outputs.astype(int).flatten(), labels_batch.numpy().flatten(),
                                                 average='macro')"""
                    running_corrects += acc.item()
                    idx += 1

            epoch_loss = running_loss / len(dataloaders[phase])
            epoch_acc = running_corrects / len(dataloaders[phase])
            if phase == 0:
                mode = "Train"
                if log:
                    writer.add_scalar("Loss/Train", epoch_loss, epoch)
                    writer.add_scalar("Acc/Train", epoch_acc, epoch)
            else:
                mode = "Val"
                if log:
                    writer.add_scalar("Loss/Validation", epoch_loss, epoch)
                    writer.add_scalar("Acc/Validation", epoch_acc, epoch)

            print('{} Loss: {:.4f} Acc: {:.4f}'.format(mode, epoch_loss, epoch_acc))

            # deep copy the model
            if phase == 1 and (epoch_acc > best_acc or epoch_loss < best_val_loss):
                print("Saving the best model weights")
                best_val_loss = epoch_loss
                best_acc = epoch_acc
                best_model_wts = copy.deepcopy(model.state_dict())

        if epoch % 10 == 0:
            print("Saving the model")
            # save the model
            torch.save(model, modelPath)
            # load best model weights
            model.load_state_dict(best_model_wts)
            torch.save(model, modelPath_bestweight)

    time_elapsed = time.time() - since
    print('Training complete in {:.0f}m {:.0f}s'.format(time_elapsed // 60, time_elapsed % 60))
    print('Best val Acc: {:4f}'.format(best_acc))

    print("Saving the model")
    # save the model
    torch.save(model, modelPath)
    # load best model weights
    model.load_state_dict(best_model_wts)
    torch.save(model, modelPath_bestweight)
