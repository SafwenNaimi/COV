import json
import trt_pose.coco
import trt_pose.models
import torch
import math
import torch2trt
from torch2trt import TRTModule
import time, sys
import cv2
import torchvision.transforms as transforms
import PIL.Image
from PIL import Image
from trt_pose.draw_objects import DrawObjects
from trt_pose.parse_objects import ParseObjects
import argparse
import os.path
import os
import numpy as np
import socket
import datetime
import time
import simpleaudio as sa


#time.sleep(50)

#HOST = '192.168.1.113' # Enter IP or Hostname of your server
#PORT = 1024 # Pick an open Port (1000+ recommended), must match the server port
#s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#s.connect((HOST,PORT))


'''
hnum: 0 based human index
kpoint : keypoints (float type range : 0.0 ~ 1.0 ==> later multiply by image width, height
'''

t=time.time()

def angle_between_points( p0, p1, p2 ):
    a = (p1[0]-p0[0])**2 + (p1[1]-p0[1])**2
    b = (p1[0]-p2[0])**2 + (p1[1]-p2[1])**2
    c = (p2[0]-p0[0])**2 + (p2[1]-p0[1])**2
    form=math.acos( (a+b-c) / math.sqrt(4*a*b) ) * 180 /math.pi
    return(form)


def get_keypoint(humans, hnum, peaks):
    #check invalid human index
    kpoint = []
    human = humans[0][hnum]
    C = human.shape[0]
    for j in range(C):
        k = int(human[j])
        if k >= 0:
            peak = peaks[0][j][k]   # peak[1]:width, peak[0]:height
            peak = (j, float(peak[0]), float(peak[1]))
            kpoint.append(peak)
            #print('index:%d : success [%5.3f, %5.3f]'%(j, peak[1], peak[2]) )
        else:    
            peak = (j, None, None)
            kpoint.append(peak)
            #print('index:%d : None %d'%(j, k) )
    return kpoint




parser = argparse.ArgumentParser(description='TensorRT pose estimation run')
parser.add_argument('--model', type=str, default='resnet', help = 'resnet or densenet' )
args = parser.parse_args()

with open('human_pose.json', 'r') as f:
    human_pose = json.load(f)

topology = trt_pose.coco.coco_category_to_topology(human_pose)

num_parts = len(human_pose['keypoints'])
num_links = len(human_pose['skeleton'])


if 'resnet' in args.model:
    print('------ model = resnet--------')
    MODEL_WEIGHTS = 'resnet18_baseline_att_224x224_A_epoch_249.pth'
    OPTIMIZED_MODEL = 'resnet18_baseline_att_224x224_A_epoch_249_trt.pth'
    model = trt_pose.models.resnet18_baseline_att(num_parts, 2 * num_links).cuda().eval()
    WIDTH = 224
    HEIGHT = 224

else:    
    print('------ model = densenet--------')
    MODEL_WEIGHTS = 'densenet121_baseline_att_256x256_B_epoch_160.pth'
    OPTIMIZED_MODEL = 'densenet121_baseline_att_256x256_B_epoch_160_trt.pth'
    model = trt_pose.models.densenet121_baseline_att(num_parts, 2 * num_links).cuda().eval()
    WIDTH = 256
    HEIGHT = 256

data = torch.zeros((1, 3, HEIGHT, WIDTH)).cuda()

if os.path.exists(OPTIMIZED_MODEL) == False:
    model.load_state_dict(torch.load(MODEL_WEIGHTS))
    model_trt = torch2trt.torch2trt(model, [data], fp16_mode=True, max_workspace_size=1<<25)
    torch.save(model_trt.state_dict(), OPTIMIZED_MODEL)

model_trt = TRTModule()
model_trt.load_state_dict(torch.load(OPTIMIZED_MODEL))

t0 = time.time()
torch.cuda.current_stream().synchronize()
for i in range(50):
    y = model_trt(data)
torch.cuda.current_stream().synchronize()
t1 = time.time()

print(50.0 / (t1 - t0))

mean = torch.Tensor([0.485, 0.456, 0.406]).cuda()
std = torch.Tensor([0.229, 0.224, 0.225]).cuda()
device = torch.device('cuda')

def preprocess(image):
    global device
    device = torch.device('cuda')
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = PIL.Image.fromarray(image)
    image = transforms.functional.to_tensor(image).to(device)
    image.sub_(mean[:, None, None]).div_(std[:, None, None])
    return image[None, ...]



 



im=cv2.imread('Squat-2.png')
im=cv2.resize(im,(400,480))
cap = cv2.VideoCapture(0) #cv2.CAP_V4L

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

ret_val, img = cap.read()

count = 0
squat_pos=0
prev_squat_pos=0
compt = 0



X_compress = 640.0 / WIDTH * 1.0
Y_compress = 480.0 / HEIGHT * 1.0


with open('testing.txt', 'r') as f:
    a=f.read()

parse_objects = ParseObjects(topology)
draw_objects = DrawObjects(topology)

while cap.isOpened()  and ((a == 'do start') or (a == 'do start\n')):  #and (count < 300)

    with open('testing.txt', 'r') as f:
        a=f.read()
    #print(os.environ['test'])
    #print(count)
    
    t_3 = time.time()
    
    
    ret_val, src = cap.read()
    if ret_val == False:
        print("Camera read Error")
        break
    src=cv2.flip(src,1) 
    img = cv2.resize(src, dsize=(WIDTH, HEIGHT), interpolation=cv2.INTER_AREA)
    #wrong=''
    #im = Image.open("pose.jpg")
    #im=cv2.imread('pose.jpg')
    #im=cv2.resize(im,(1000,1000))
    
    
    color = (0, 255, 0)
    data = preprocess(img)
    cmap, paf = model_trt(data)
    cmap, paf = cmap.detach().cpu(), paf.detach().cpu()
    counts, objects, peaks = parse_objects(cmap, paf)#, cmap_threshold=0.15, link_threshold=0.15)
    fps = 1.0 / (time.time() - t_3)
    command='*'
    command_2='*'
    command_3='*'
    command_4='*'
    
    #wrong=''
    #wrong_2=''
    #wrong_3=''
    #wrong_4=''
    
    
    for i in range(counts[0]):
        pnts = []
        pntss = []
        pntsss = []
        pntssss = []
        pntsssss = [] 
        pntssssss = []
        pntsssssss = []
        keypoints = get_keypoint(objects, i, peaks)
        #print(keypoints)
        for j in range(len(keypoints)):
            
            #print(keypoints[j][1])
            if keypoints[j][1]:
                x = round(keypoints[j][2] * WIDTH * X_compress)
                y = round(keypoints[j][1] * HEIGHT * Y_compress)
                #print(j,x,y)
                #cv2.circle(src, (x, y), 3, color, 2)
                #cv2.putText(src , "%d" % int(keypoints[j][0]), (x + 5, y),  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 1)
                if (j==6) or (j==8) or (j==10):
                    #cv2.circle(src, (x, y), 3, color, 4)
                    #cv2.putText(src , "%d" % int(keypoints[j][0]), (x + 5, y),  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 1)
                    pnts.append(((x * 640 ), (y * 480)))
                if (j==5) or (j==7) or (j==9):
                    #cv2.circle(src, (x, y), 3, color, 4)
                    #cv2.putText(src , "%d" % int(keypoints[j][0]), (x + 5, y),  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 1)
                    pntss.append(((x * 640 ), (y * 480)))
                #print(len(pnts))

                if (j==12) or (j==14) or (j==16):
                    #cv2.circle(src, (x, y), 3, color, 4)
                    #cv2.putText(src , "%d" % int(keypoints[j][0]), (x + 5, y),  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 1)
                    pntsss.append(((x * 640 ), (y * 480)))

                if (j==11) or (j==13) or (j==15):
                    #cv2.circle(src, (x, y), 3, color, 4)
                    #cv2.putText(src , "%d" % int(keypoints[j][0]), (x + 5, y),  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 1)
                    pntssss.append(((x * 640 ), (y * 480)))
                if (j==11) or (j==15) or (j==12):
                    #cv2.circle(src, (x, y), 3, color, 8)
                    #cv2.putText(src , "%d" % int(keypoints[j][0]), (x + 5, y),  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 1)
                    pntsssss.append(((x * 640 ), (y * 480)))
                if (j==7) or (j==5) or (j==11):
                    #cv2.circle(src, (x, y), 3, color, 8)
                    #cv2.putText(src , "%d" % int(keypoints[j][0]), (x + 5, y),  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 1 )
                    pntssssss.append(((x * 640 ), (y * 480)))
                if (j==8) or (j==6) or (j==12):
                    #cv2.circle(src, (x, y), 3, color, 8)
                    #cv2.putText(src , "%d" % int(keypoints[j][0]), (x + 5, y),  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 1 )
                    pntsssssss.append(((x * 640 ), (y * 480)))

               


            
                if (len(pntsss)==3) and (len(pntssss)==3)  :
                    angleeee = (angle_between_points(pntssss[0], pntssss[1], pntssss[2]))
                    angleee = (angle_between_points(pntsss[0], pntsss[1], pntsss[2]))  
                    
                    squat_pos = 1 if angleee <= 100 else 0
                    if prev_squat_pos - squat_pos == 1:
                        compt +=1
                        
            
                    prev_squat_pos = squat_pos
                        
                    if ((round(angleeee)) <= 100)  and ((round(angleee)) <= 100): 
                    
                        cv2.line(src,(round(keypoints[12][2] * WIDTH * X_compress), round(keypoints[12][1] * HEIGHT * Y_compress)),(round(keypoints[14][2] * WIDTH * X_compress), round(keypoints[14][1] * HEIGHT * Y_compress)),(102,200,111),2)
                        cv2.line(src,(round(keypoints[14][2] * WIDTH * X_compress), round(keypoints[14][1] * HEIGHT * Y_compress)),(round(keypoints[16][2] * WIDTH * X_compress), round(keypoints[16][1] * HEIGHT * Y_compress)),(102,200,111),2) 
                        cv2.line(src,(round(keypoints[11][2] * WIDTH * X_compress), round(keypoints[11][1] * HEIGHT * Y_compress)),(round(keypoints[13][2] * WIDTH * X_compress), round(keypoints[13][1] * HEIGHT * Y_compress)),(102,200,111),2)
                        cv2.line(src,(round(keypoints[13][2] * WIDTH * X_compress), round(keypoints[13][1] * HEIGHT * Y_compress)),(round(keypoints[15][2] * WIDTH * X_compress), round(keypoints[15][1] * HEIGHT * Y_compress)),(102,200,111),2) 
                        cv2.circle(src, (round(keypoints[12][2] * WIDTH * X_compress), round(keypoints[12][1] * HEIGHT * Y_compress)), 3, (102,200,111), 2)
                        cv2.circle(src, (round(keypoints[11][2] * WIDTH * X_compress), round(keypoints[11][1] * HEIGHT * Y_compress)), 3, (102,200,111), 2)
                        if command[(len(command))-1]!='j':
                            command = (command+'j')[:3]
                        

                    else:
                        cv2.line(src,(round(keypoints[12][2] * WIDTH * X_compress), round(keypoints[12][1] * HEIGHT * Y_compress)),(round(keypoints[14][2] * WIDTH * X_compress), round(keypoints[14][1] * HEIGHT * Y_compress)),(66,66,234),2)
                        cv2.line(src,(round(keypoints[14][2] * WIDTH * X_compress), round(keypoints[14][1] * HEIGHT * Y_compress)),(round(keypoints[16][2] * WIDTH * X_compress), round(keypoints[16][1] * HEIGHT * Y_compress)),(66,66,234),2) 
                        cv2.line(src,(round(keypoints[11][2] * WIDTH * X_compress), round(keypoints[11][1] * HEIGHT * Y_compress)),(round(keypoints[13][2] * WIDTH * X_compress), round(keypoints[13][1] * HEIGHT * Y_compress)),(66,66,234),2)
                        cv2.line(src,(round(keypoints[13][2] * WIDTH * X_compress), round(keypoints[13][1] * HEIGHT * Y_compress)),(round(keypoints[15][2] * WIDTH * X_compress), round(keypoints[15][1] * HEIGHT * Y_compress)),(66,66,234),2)
                        cv2.rectangle(src, (round(keypoints[12][2] * WIDTH * X_compress), round(keypoints[12][1] * HEIGHT * Y_compress)),((round(keypoints[12][2] * WIDTH * X_compress)+10), (round(keypoints[12][1] * HEIGHT * Y_compress)+10)), (66,66,234), 2)
                        cv2.rectangle(src, (round(keypoints[11][2] * WIDTH * X_compress), round(keypoints[11][1] * HEIGHT * Y_compress)),((round(keypoints[11][2] * WIDTH * X_compress)+10), (round(keypoints[11][1] * HEIGHT * Y_compress)+10)), (66,66,234), 2)
                        

                    
                    

                        
                        
                    
                        
                            

               
               

                


        
    c=str(round(count/10))
               
    cv2.putText(src , "FPS: %f" % (fps), (20, 20),  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 1)
    #h=cv2.resize(src,(1000,1000))
    key=np.hstack([src,im])
    #key=np.hstack([h,im])
    cv2.putText(key , "COUNTER: "+c, (780, 950),cv2.FONT_HERSHEY_SIMPLEX, 1, (56, 127, 224), 2,cv2.LINE_AA)
    cv2.putText(key , "Number Of Squats "+str(compt), (20, 40),cv2.FONT_HERSHEY_SIMPLEX, 1, (56, 127, 224), 2,cv2.LINE_AA)
    
    cv2.rectangle(key, (775,900), (995,980), (56,58,57), 4)
    cv2.namedWindow ('key', cv2.WINDOW_NORMAL)
    cv2.setWindowProperty ('key', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.imshow('key',key)
    

    
    cv2.waitKey(20)
      
    
    #j=(i.replace('*', ''))
    nn=(command.replace('*', ''))
    
    
        
       
            

    
    with open('aghlat.txt', 'w') as f:
        f.write('%s' % command)
    #print(j)
    #with open('aghlat.txt', 'w') as f:
        #f.write('%s' % f)

    
            
    
    
    
    
    

    ###print(round(count/10))
    #calcul(dst)
    #cv2.imshow('dgfgd',im)
    count += 1
    #print('*****')


cv2.destroyAllWindows()
cap.release()
