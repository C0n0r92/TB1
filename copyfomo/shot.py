import sys
from PIL import ImageGrab
ImageGrab.grab(xdisplay=':5').save('/workspace/copyfomo/screens/'+sys.argv[1]+'.png')
