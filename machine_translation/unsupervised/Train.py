from __future__ import unicode_literals, print_function, division
from io import open

import string
import re
import random
import numpy as np
import os
import time
import math

import matplotlib.pyplot as plt
plt.switch_backend('agg')
import matplotlib.ticker as ticker

import torch
import torch.nn as nn
from torch import optim
import torch.nn.functional as F

from EncoderRNN import EncoderRNN
from DecoderRNN import DecoderRNN
from Pretrained_embedding import pre_embedding






def trainBatch(tensor_1, input_length_1, 
               tensor_2, input_length_2, 
               style_1, style_2, 
               encoder, decoder, mode,
               encoder_optimizer=None, decoder_optimizer=None, cnn_optimizer=None, tearcher_enforce_rate=0.5, textCNN=None, device=None):

    # input_tensors (batch, seq)
    # target_tensors (batch, seq)
    # input_lengths (batch)
    
    total_loss = 0
    rec_loss = 0
    cnn_loss = 0
    log_criterion = nn.NLLLoss()
    
    if mode=='train':
        encoder.train()
        decoder.train()
        textCNN.train()
            
        encoder_optimizer.zero_grad()
        decoder_optimizer.zero_grad()
        cnn_optimizer.zero_grad()
    
    elif mode=='val':
        encoder.eval()
        decoder.eval()
        textCNN.eval()
        
    else:
        raise ValueError('wrong mode')
        

    # outputs (seq, batch, hidden_size)
    # h: (num_layers, batch, hidden_size)
    # decoder_outputs: batch, seq, vocab
    # output_seq: batch, seq
    
    
    
    
    input_lengths_1, indices = torch.sort(input_length_1, descending=True)
    order = torch.LongTensor(range(len(input_length_1)))
    order_1 = order[indices]
    tensors_1 = tensor_1[indices,:]
    tensors_2 = tensor_2[indices,:]
    
    encoder_outputs_1, encoded_h = encoder.forward(tensors_1, input_lengths_1, style_1)
    decoder_outputs_1, output_seq_1_1 = decoder.forward(encoded_h, encoder_outputs_1, style_1, tensors_1, tearcher_enforce_rate)
    decoder_outputs_2, output_seq_1_2 = decoder.forward(encoded_h, encoder_outputs_1, style_2, tensors_2, tearcher_enforce_rate)

    batch_size, output_len_1, _ = decoder_outputs_1.size()
    batch_size, output_len_2, _ = decoder_outputs_2.size()
        
    for i in range(batch_size):
        
        rec_loss += log_criterion(decoder_outputs_1[i], tensors_1[i,:output_len_1])
        rec_loss += log_criterion(decoder_outputs_2[i], tensors_2[i,:output_len_2])
        
    input_lengths_2, indices = torch.sort(input_length_2, descending=True)
    order = torch.LongTensor(range(len(input_length_2)))
    order_2 = order[indices]
    tensors_1 = tensor_1[indices,:]
    tensors_2 = tensor_2[indices,:]
    
    encoder_outputs_2, encoded_h = encoder.forward(tensors_2, input_lengths_2, style_2)
    decoder_outputs_2, output_seq_2_2 = decoder.forward(encoded_h, encoder_outputs_2, style_2, tensors_2, tearcher_enforce_rate)
    decoder_outputs_1, output_seq_2_1 = decoder.forward(encoded_h, encoder_outputs_2, style_1, tensors_1, tearcher_enforce_rate)
    
    batch_size, output_len_1, _ = decoder_outputs_1.size()
    batch_size, output_len_2, _ = decoder_outputs_2.size()
        
    for i in range(batch_size):

        rec_loss += log_criterion(decoder_outputs_1[i], tensors_1[i,:output_len_1])
        rec_loss += log_criterion(decoder_outputs_2[i], tensors_2[i,:output_len_2])
            
    # batch, 2
    cnn_output_1 = textCNN.forward(tensor_1)
    cnn_output_2 = textCNN.forward(tensor_2)
    
    _, predict_1 = cnn_output_1.topk(1)
    _, predict_2 = cnn_output_2.topk(1)
    
    correct_pred_1 = torch.sum(predict_1.detach().squeeze()==0).cpu().numpy()
    correct_pred_2 = torch.sum(predict_2.detach().squeeze()==1).cpu().numpy()
   
    cnn_loss += log_criterion(cnn_output_1, torch.zeros(batch_size).type(torch.long).to(device))
    cnn_loss += log_criterion(cnn_output_2, torch.ones(batch_size).type(torch.long).to(device))
    
    
            
    if mode=='train':
        rec_loss.backward()
        cnn_loss.backward()

        encoder_optimizer.step()
        decoder_optimizer.step()
        cnn_optimizer.step()
        
        return rec_loss.item(),cnn_loss.item(), (correct_pred_1,correct_pred_2, batch_size)
    
    else:
        output_seq = []
        for i in range(len(output_seq_1_1)):
            output_seq.append([tensor_1.cpu().numpy()[i], output_seq_1_1[order_1].cpu().numpy()[i], output_seq_1_2[order_1].cpu().numpy()[i], tensor_2.cpu().numpy()[i], output_seq_2_1[order_2].cpu().numpy()[i], output_seq_2_2[order_2].cpu().numpy()[i]])
            
        return rec_loss.item(), cnn_loss.item(), output_seq, (correct_pred_1,correct_pred_2, batch_size)#, atten.cpu().numpy()
    
    
    
def trainEpoch(tensor_1, input_length_1, 
               tensor_2, input_length_2, 
               style_1, style_2, 
               encoder, decoder, encoder_optimizer, decoder_optimizer, cnn_optimizer,
               epoches, batch_size, tearcher_enforce_rate, textCNN, device=None):
    
    # input_train_tensors: batch, seq
    train_size = len(tensor_1)
    orders = np.arange(train_size)
    np.random.shuffle(orders)
    total_rec_loss = 0.0
    total_cnn_loss = 0.0
    total_correct = 0.0

    for i in range(0, train_size, batch_size):
        
        temp = i+batch_size

        if temp >= train_size: 
            batch = orders[i:train_size]
        else:
            batch = orders[i:i+batch_size]

        tensors_1 = tensor_1[batch]
        input_lengths_1 = input_length_1[batch]
        tensors_2 = tensor_2[batch]
        input_lengths_2 = input_length_2[batch]

        rec_loss, cnn_loss, (correct_pred_1,correct_pred_2, total) = trainBatch(tensors_1, input_lengths_1, tensors_2, input_lengths_2, style_1, style_2, 
                          encoder, decoder, 'train', encoder_optimizer, decoder_optimizer, cnn_optimizer, tearcher_enforce_rate, textCNN, device)


        print('\r' + str(i) + '/' + str(train_size)+', reconstruction loss: ' + str(rec_loss/len(batch)) + 
              ' classication loss: ' + str(cnn_loss/len(batch)) + ' classfication accuracy: ' + str((correct_pred_1+correct_pred_2)/(2.0*total)), end='')
        
        total_correct+=correct_pred_1
        total_correct+=correct_pred_2
        total_rec_loss += rec_loss
        total_cnn_loss += cnn_loss
        
        #torch.cuda.empty_cache()
    print()
    return total_rec_loss/train_size, total_cnn_loss/train_size, total_correct/(2.0*train_size)

def evaluate(tensor_1, input_length_1, 
             tensor_2, input_length_2, 
             style_1, style_2, 
             encoder, decoder, tearcher_enforce_rate, textCNN, device=None):
    

    batch_size = 64
    total_rec_loss = 0.0
    total_cnn_loss = 0.0
    total_correct = 0.0
    train_size, _ = tensor_1.size()
    accuracy = 0
    
    outputs = []
    #attns = []
        
    orders = np.arange(train_size)
    
    with torch.no_grad():

        for i in range(0, train_size, batch_size):
            temp = i+batch_size

            if temp >= train_size: 
                batch = orders[i:train_size]

            else:
                batch = orders[i:i+batch_size]

            tensors_1 = tensor_1[batch]
            input_lengths_1 = input_length_1[batch]
            tensors_2 = tensor_2[batch]
            input_lengths_2 = input_length_2[batch]


            rec_loss, cnn_loss, output_seq, (correct_pred_1,correct_pred_2, total) = trainBatch(tensor_1=tensors_1, input_length_1=input_lengths_1, 
                                                                                                tensor_2=tensors_2, input_length_2=input_lengths_2, 
                                                                                                style_1=style_1, style_2=style_2, 
                                                                                                encoder=encoder, decoder=decoder, mode='val',
                                                                                                encoder_optimizer=None, decoder_optimizer=None, 
                                                                                                cnn_optimizer=None, 
                                                                                                tearcher_enforce_rate=tearcher_enforce_rate, 
                                                                                                textCNN=textCNN, device=device)

            print('\r' + 'Evalidation: '+ str(i) + '/' + str(train_size)+', loss:' + str(rec_loss/len(batch))+ 
              ' classication loss: ' + str(cnn_loss/len(batch)) + ' classfication accuracy: ' + str((correct_pred_1+correct_pred_2)/(2.0*total)), end='')

            total_rec_loss += rec_loss
            total_cnn_loss += cnn_loss
            total_correct += correct_pred_1
            total_correct += correct_pred_2
            outputs += output_seq
            #attns.append(attn)
        
    print()        
    return total_rec_loss/train_size, total_cnn_loss/train_size, total_correct/(2.0*train_size), outputs#, np.concatenate(outputs, axis=0)#, np.asarray(attns)



def train(tensors_1, input_lengths_1, tensors_2, input_lengths_2, 
          tensors_1_val, input_lengths_1_val, tensors_2_val, input_lengths_2_val, 
          style_1, style_2, 
          encoder, decoder, encoder_optimizer, decoder_optimizer, cnn_optimizer, 
          epoches=20, batch_size=64, print_every=1, plot_every=1,
          patience = 5, decay_rate=0.5, early_stop=10, sp_user=None, textCNN=None, device=None):
    
    # input_val, input_val_lengths, output_val,
              
    start = time.time()
    plot_train_rec_loss = []
    plot_train_cnn_loss = []
    plot_train_cnn_acc = []
    plot_val_cnn_loss = []
    plot_val_rec_loss = []
    plot_val_cnn_acc = []
    
    patience_count = 0
    early_stop_count = 0

        
    best_rec_val_loss = 100
    best_cnn_val_acc = 0.0
    
    for iter in range(1, epoches + 1):
        
        tearcher_enforce_rate = np.max(1 - 2 * (1.0*iter/epoches), 0)
        print('tearcher_enforce_rate:', tearcher_enforce_rate)
        
        print('iter', iter)
            
        train_rec_loss, train_cnn_loss, train_cnn_acc = trainEpoch(tensors_1, input_lengths_1, tensors_2, input_lengths_2, style_1, style_2, 
                                encoder, decoder, encoder_optimizer, decoder_optimizer, cnn_optimizer,
                                epoches, batch_size, tearcher_enforce_rate, textCNN, device)

        val_rec_loss, val_cnn_loss, val_cnn_acc, output_seq = evaluate(tensors_1_val, input_lengths_1_val, tensors_2_val, input_lengths_2_val, 
                                        style_1, style_2, encoder, decoder, 0.0, textCNN, device)

            
        with open('./saved_models/val_result_'+str(iter), 'w') as f:
            for i in range(len(output_seq)):
                for j in range(6):
                    f.write(sp_user.decode_ids(output_seq[i][j].tolist()) + '\n')
                f.write('\n')
                
        if iter % print_every == 0:
            print(timeSince(start, iter / epoches) + 
                  ' /ntrain rec loss: %5.3f.  val rec loss: %5.3f. /ntrain cnn loss: %5.3f.  val cnn loss: %5.3f. /ntrain cnn acc: %5.3f.  val cnn acc: %5.3f. '
                  % (train_rec_loss, train_cnn_loss,train_cnn_loss, val_cnn_loss, train_cnn_acc, val_cnn_acc))
            

        if iter % plot_every == 0:
            plot_train_rec_loss.append(train_rec_loss)
            plot_train_cnn_loss.append(train_cnn_loss)
            plot_train_cnn_acc.append(train_cnn_acc)
            plot_val_cnn_loss.append(val_cnn_loss)
            plot_val_rec_loss.append(val_rec_loss)
            plot_val_cnn_acc.append(val_cnn_acc)
  
            
        
        if val_rec_loss<best_rec_val_loss:
            patience_count = 0
            early_stop_count = 0
            print('val loss decreases from %5.3f to %5.3f, save models'% (best_rec_val_loss, val_rec_loss))
            torch.save(encoder, './saved_models/encoder.pt')
            torch.save(decoder, './saved_models/decoder.pt')
            torch.save(encoder_optimizer, './saved_models/encoder_optimizer.pt')
            torch.save(decoder_optimizer, './saved_models/decoder_optimizer.pt')
            np.savetxt('./saved_models/embedding', encoder.embedding.weight.detach().cpu().numpy(), delimiter=',')

            #torch.save(decoder.attn, './saved_models/attn.pt')

            best_rec_val_loss = val_rec_loss
        else: 
            patience_count+=1
            early_stop_count+=1
            
        if best_cnn_val_acc<val_cnn_acc:
            print('val cnn acc increase from %5.3f to %5.3f, save models'% (best_cnn_val_acc, val_cnn_acc))
            torch.save(textCNN, './saved_models/textCNN.pt')
            torch.save(cnn_optimizer, './saved_models/cnn_optimizer.pt')

            best_cnn_val_acc = val_cnn_acc

        #showAttention(input_val_tensors[100],output_seq[100], attn[100])
        if patience_count>= patience:
            adjust_learning_rate(encoder_optimizer, decay_rate)
            adjust_learning_rate(decoder_optimizer, decay_rate)
            adjust_learning_rate(cnn_optimizer, decay_rate)
            
        # early stop
        if early_stop_count>= early_stop:
            print()
            print('Early Etop')
            break
            
        for i in range(6):
            print(sp_user.decode_ids(output_seq[5][i].tolist()))
            
        print()
        
        with open('./saved_models/training_data', 'w') as f:
            f.write('train_rec_loss, val_rec_loss, train_cnn_loss, val_cnn_loss, train_cnn_acc, val_cnn_acc\n')
            for i in range(len(plot_train_rec_loss)):
                f.write(str(plot_train_rec_loss[i]) +', '+str(plot_val_rec_loss[i])+
                        ', '+str(plot_train_cnn_loss[i])+', '+str(plot_val_cnn_loss[i])+
                        ', '+str(plot_train_cnn_acc[i])+', '+str(plot_val_cnn_acc[i]) +'\n')
        
        
        
    the_encoder = torch.load('./saved_models/encoder.pt')
    the_decoder = torch.load('./saved_models/decoder.pt')
    the_cnn = torch.load('./saved_models/textCNN.pt')
    the_encoder_optimizer = torch.load('./saved_models/encoder_optimizer.pt')
    the_decoder_optimizer = torch.load('./saved_models/decoder_optimizer.pt')
    the_cnn_optimizer = torch.load('./saved_models/cnn_optimizer.pt')
    #the_attn = torch.load('./saved_models/attn.pt')
    
    
    #print('./saved_models/encoder' + str(best_val_loss) + '.pt')
    torch.save(the_encoder, './saved_models/encoder' + str(best_rec_val_loss) + '.pt')
    torch.save(the_decoder, './saved_models/decoder' + str(best_rec_val_loss) + '.pt')
    torch.save(the_cnn, './saved_models/cnn' + str(best_cnn_val_acc) + '.pt')
    torch.save(the_encoder_optimizer, './saved_models/encoder_optimizer' + str(best_rec_val_loss) + '.pt')
    torch.save(the_decoder_optimizer, './saved_models/decoder_optimizer' + str(best_rec_val_loss) + '.pt')
    torch.save(the_cnn_optimizer, './saved_models/cnn_optimizer' + str(best_cnn_val_acc) + '.pt')

    #torch.save(the_attn, './saved_models/attn' + str(best_val_loss) + '.pt')
    

    showPlot([plot_train_rec_loss,plot_val_rec_loss],['train_rec_loss','val_rec_loss'] )
    showPlot([plot_train_cnn_loss,plot_val_cnn_loss],['train_cnn_loss','val_cnn_loss'] )
    showPlot([plot_train_cnn_acc,plot_val_cnn_acc],['train_cnn_acc','val_cnn_acc'] )
    
    return output_seq, plot_train_rec_loss,plot_val_rec_loss,plot_train_cnn_loss,plot_val_cnn_loss,plot_train_cnn_acc,plot_val_cnn_acc
    
    
def asMinutes(s):
    m = math.floor(s/60)
    s -= m*60
    return '%dm %ds' % (m, s)

def timeSince(since, precent):
    now = time.time()
    s = now - since
    es = s / precent
    rs = es - s 
    return '%s (- %s)' % (asMinutes(s), asMinutes(rs))

def showPlot(value_list, name_list):
    plt.figure()
    fig, ax = plt.subplots()
    # this locator puts ticks at regular intervals
    loc = ticker.MultipleLocator(base=1)
    ax.xaxis.set_major_locator(loc)
    
    for i in range(len(value_list)):
        plt.plot(value_list[i], label=name_list[i])

    plt.legend()
    plt.xlabel("Epoch")


    
def showAttention(input_sentence, output_sentence, attentions):
    # Set up figure with colorbar
    fig = plt.figure()
    ax = fig.add_subplot(111)
    cax = ax.matshow(attentions, cmap='bone')
    fig.colorbar(cax)

    # Set up axes
    ax.set_xticklabels([''] + input_sentence +
                       ['<EOS>'], rotation=90)
    ax.set_yticklabels([''] + output_sentence)

    # Show label at every tick
    ax.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.yaxis.set_major_locator(ticker.MultipleLocator(1))

    plt.show()
    
def adjust_learning_rate(optimizer, ratio):
    for param_group in optimizer.param_groups:
        param_group['lr'] = param_group['lr'] *  ratio

    



