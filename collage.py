#!/usr/bin/env python3
from PIL import Image, ImageEnhance, ImageDraw, ImageFont
from PIL import JpegImagePlugin
import cv2
import sys
import os 
import math
import bisect

# Workaround to make sure we open JPEG as JPEG
JpegImagePlugin._getmp = lambda: None

def hex_to_rgb(hex):
    rgb = []
    for i in (0, 2, 4):
        decimal = int(hex[i:i+2], 16)
        rgb.append(decimal)
    return tuple(rgb)

class ImageTransform:
    operation = "Zoom"
    factor_1 = 1
    factor_2 = 0
    factor_3 = 0

    def __init__(self):
        pass

    def __init__(self, operation="Zoom", factor_1=1, factor_2=0, factor_3=0):
        self.operation = operation
        self.factor_1 = factor_1
        self.factor_2 = factor_2 
        self.factor_3 = factor_3

    def apply(self, inputImg, targetDimensions, color=None):
        a, b = inputImg.size
        c, d = targetDimensions
        if not color:
            color='blue'
        if self.operation == "Zoom":
            return inputImg.resize((int(a * self.factor_1), int(b * self.factor_1)))
        if self.operation == "Move":
            res = Image.new('RGBA', inputImg.size, color=color)
            res.putalpha(0)
            deltaA = int(self.factor_1 * a)
            deltaB = int(self.factor_2 * b)
            pasteCoords = (deltaA, deltaB)
            res.paste(inputImg, pasteCoords)
            return res
        if self.operation == "Margin":
            # Zoom out by factor 
            # Then paste and crop
            margin = int(self.factor_1 * min(c, d))
            cropDimensions = (margin, margin, c - margin, d - margin)
            zoomedOut = inputImg.crop(cropDimensions) # .resize(targetDimensions)
            newImage = Image.new('RGBA', targetDimensions) # , color=color)
            newImage.putalpha(0)
            newImage.paste(zoomedOut, (margin, margin), zoomedOut)
            return newImage
        if self.operation == "FixedMargin":
            # Zoom out by factor 
            # Then paste and crop
            margin = self.factor_1
            cropDimensions = (margin, margin, c - margin, d - margin)
            zoomedOut = inputImg.crop(cropDimensions) # .resize(targetDimensions)
            newImage = Image.new('RGBA', targetDimensions) # , color=color)
            newImage.putalpha(0)
            newImage.paste(zoomedOut, (margin, margin))
            return newImage



        # Default is identity
        return inputImg

class DivisionGraph:
    isFinal = True
    division = None
    splitPercent = None
    children = []
    image = None
    imgTransforms = []
    
    def setImages(self, imgList, imgTransform):
        print(imgList, imgTransform)
        if self.isFinal:
            if imgList:
                self.image = imgList[0]
                if imgTransform:
                    self.imgTransforms = imgTransform[0]
                return 1
            else:
                return 0
        else:
            assert(len(self.children) == 2)
            n = self.children[0].setImages(imgList, imgTransform)
            m = self.children[1].setImages(imgList[n:], imgTransform[n:])
            return (n + m)


    def divideHorizontally(self, splitPercent=0.5):
        self.isFinal = False
        self.division = "H"
        self.splitPercent = splitPercent
        self.children = [DivisionGraph(), DivisionGraph()]
    
    def divideVertically(self, splitPercent=0.5):
        self.isFinal = False
        self.division = "V"
        self.splitPercent = splitPercent
        self.children = [DivisionGraph(), DivisionGraph()]
    
    def __repr__(self):
        if self.isFinal:
            if self.image:
                return "i"
            else:
                return "o"
        else:
            return f"[{self.division.join([repr(x) for x in self.children])}]"
    
    def toImage(self, size_x, size_y, count=1, color=(0, 0, 255)):
        n = 0
        img = Image.new('RGBA', (size_x, size_y), color=color)
        img.putalpha(0)
        if self.isFinal:
            print(f"Final image {count} - size {size_x}, {size_y}")
            if self.image:
                a = size_x
                b = size_y
                c = self.image.size[0]
                d = self.image.size[1]
                if a * d < b * c:
                    ratio = b / d
                    # a / b > c / d, use b as main dimension
                else:
                    # Use a as main dimension
                    ratio = a / c
                dim_x = int(c * ratio)
                dim_y = int(d * ratio)
                print(f"Resizing {self.image.size} to {dim_x, dim_y}")
                newImage = self.image.resize((dim_x, dim_y))
                for t in self.imgTransforms:
                    newImage = t.apply(newImage, targetDimensions = (a, b), color=color)
                img.paste(newImage, (0, 0), newImage)

            else:
                d = ImageDraw.Draw(img)
                fntSize = int(min(size_x, size_y) / 3)
                fnt = ImageFont.truetype('/Library/Fonts/Arial.ttf', fntSize)
                d.text((int(size_x / 3), int(size_y / 3)), str(count), fill = (255, 255, 255), font=fnt)
            n = 1
        else:
            assert(len(self.children) == 2)
            if self.division == "H":
                size_1_x = size_x
                size_2_x = size_x
                size_1_y = int(self.splitPercent * size_y)
                size_2_y = size_y - size_1_y
                pasteCoords = (0, size_1_y)
            else:
                size_1_x = int(self.splitPercent * size_x)
                size_2_x = size_x - size_1_x
                size_1_y = size_y
                size_2_y = size_y
                pasteCoords = (size_1_x, 0)
            color_1 = (color[0], color[1], int(color[2] / 2))
            color_2 = (color[0], color[1], int(3 * color[2] / 4))
            img1, n1 = self.children[0].toImage(size_1_x, size_1_y, count, color_1)
            img2, n2 = self.children[1].toImage(size_2_x, size_2_y, count + n1, color_2)
            img.paste(img1, (0, 0), img1)
            img.paste(img2, pasteCoords, img2)
            n = n1 + n2
        return img, n

class Grid:
    size_x = 800
    size_y = 800
    legend_factor = 1.13875
    legend = ""
    fillColor = hex_to_rgb("75161E")
    # fillColor = hex_to_rgb("A22F6A")
    
    # fillColor = (0x7F, 0x22, 0x05)  # 7F2205
    textColor = (32, 32, 32)
    textColor = (196, 196, 196)
    textColor = (220, 220, 220)

    repartitionGraph = DivisionGraph()

    def __init__(self):
        pass

    def __repr__(self):
        return f"Grid({self.size_x}x{self.size_y}) : {self.repartitionGraph}"
    
    def loadImages(self, path):
        res = []
        for fName in os.listdir(path):
            img = Image.open(os.path.join(path, fName))
            res.append(img)
        return res
    
    def gen(self):
        outImg, _ = self.repartitionGraph.toImage(self.size_x, self.size_y, color=self.fillColor)
        outImg.show()
    
    def saveAsJpeg(self, outputFileName):
        outImg, _ = self.repartitionGraph.toImage(self.size_x, self.size_y, color=self.fillColor)
        outImg.save(outputFileName, "JPEG")

    def saveAsJpegWithLegend(self, outputFileName):
        outImg, _ = self.repartitionGraph.toImage(self.size_x, self.size_y, color=self.fillColor)
        print("outImg: ", outImg)
        heightLegend = int(self.size_y * (self.legend_factor - 1))
        fullImage_dim = (self.size_x, self.size_y + heightLegend)
        
        newImage = Image.new('RGBA', fullImage_dim) #, color=self.fillColor)
        newImage.putalpha(0)

        # Add background
        color_1 = hex_to_rgb("812627")
        color_2 = hex_to_rgb("8B292A") #  631D1E
        color_3 = hex_to_rgb("621D1E")
        color_4 = hex_to_rgb("671E20")
        colors = [color_1, color_2, color_3, color_4]
        ranges = [0, 0.5, 0.9, 1]
        print("Generating background with a beautiful gradient")
        im = genRadialRadient(fullImage_dim, (fullImage_dim[0] / 2, fullImage_dim[1] / 2), colors, ranges)
        newImage.paste(im, (0, 0), im)
        print("newImage with gradient: ", newImage)
        rgb_im = newImage.convert('RGB')
        # outImg.save(outputFileName, "JPEG")
        rgb_im.save(outputFileName, "JPEG")
        newImage.paste(outImg, (0, 0), outImg)
        drawer = ImageDraw.Draw(newImage)
        fntSize = int(3  * heightLegend / 5)
        # fntSize = int(2  * heightLegend / 5)
        fnt = ImageFont.truetype('/System/Library/Fonts/Supplemental/SnellRoundhand.ttc', fntSize)
        a, b, c, d = drawer.textbbox((0, 0), self.legend, font=fnt)
        print(fntSize, a, b, c, d, self.size_x, self.size_y, heightLegend)
        textCoords = ((self.size_x - (c - a)) / 2, self.size_y - b + (heightLegend - (d - b)) / 2)
        strokeColor = tuple([int((self.fillColor[i] + self.textColor[i])/2) for i in range(3)])
        drawer.text(textCoords, self.legend, fill = self.textColor, font=fnt, stroke_width=4, stroke_fill="black")

        # newImage.show()
        # newImage.save("new.jpg", "JPEG")
        print("newImage with text: ", newImage)
        rgb_im = newImage.convert('RGB')
        rgb_im.save("new.jpg", "JPEG")


def generateGrid():
    return Grid()

def collage2023_1():
    grid = generateGrid()
    grid.size_x = 800
    grid.size_y = 800
    print(grid)
    grid.repartitionGraph.divideVertically(0.7)
    grid.repartitionGraph.children[0].divideHorizontally(0.35)
    grid.repartitionGraph.children[0].children[1].divideHorizontally(0.6)
    grid.repartitionGraph.children[0].children[1].children[0].divideVertically(0.4)
    grid.repartitionGraph.children[1].divideHorizontally(0.4)
    print(grid)
    l = grid.loadImages("./carte2023")
    permutation = [5, 0, 1, 3, 4, 2]
    ordered_images = [l[permutation[i]] for i in range(6)]
    # ordered_images = []
    transforms = []
    transforms.append([ImageTransform("Move", 0, -0.15)]) # Image 1 
    transforms.append([ImageTransform("Zoom", 1.05), ImageTransform("Move", -0.05, -0.005)]) # Image 2
    transforms.append([ImageTransform("Zoom", 1.7), ImageTransform("Move", -.15, -.35)]) # Image 3
    transforms.append([ImageTransform("Move", 0, -.25)]) # Image 4
    transforms.append([]) # Image 5
    transforms.append([ImageTransform("Move", -0.18, 0)]) # Image 6
    for t in transforms:
        t.append(ImageTransform("FixedMargin", int(grid.size_x / 200)))
    grid.repartitionGraph.setImages(ordered_images, transforms)
    print(grid)
    grid.gen()
    return grid

def collage2023_2():
    grid = generateGrid()
    grid.size_x = 800
    grid.size_y = 800
    print(grid)
    grid.repartitionGraph.divideVertically(0.7)
    grid.repartitionGraph.children[0].divideHorizontally(0.38)
    grid.repartitionGraph.children[0].children[1].divideVertically(0.4)
    grid.repartitionGraph.children[0].children[1].children[1].divideHorizontally(0.6)
    grid.repartitionGraph.children[1].divideHorizontally(0.4)
    print(grid)
    l = grid.loadImages("./carte2023")
    permutation = [5, 0, 1, 3, 4, 2]
    ordered_images = [l[permutation[i]] for i in range(6)]
    transforms = []
    transforms.append([ImageTransform("Move", 0, -0.15)]) # Image 1 
    transforms.append([ImageTransform("Zoom", 1), ImageTransform("Move", -0.15, -0.005)]) # Image 2
    transforms.append([ImageTransform("Zoom", 1.7), ImageTransform("Move", -.15, -.35)]) # Image 3
    transforms.append([ImageTransform("Zoom", 1.7), ImageTransform("Move", -0.22, -.25)]) # Image 4
    transforms.append([]) # Image 5
    transforms.append([ImageTransform("Move", -0.18, 0)]) # Image 6
    for t in transforms:
        t.append(ImageTransform("FixedMargin", int(grid.size_x / 200)))
    grid.repartitionGraph.setImages(ordered_images, transforms)
    print(grid)
    grid.gen()
    return grid

def collage2023_3():
    grid = generateGrid()
    grid.size_x = 3200
    grid.size_y = 3200
    # grid.legend="Bonne ann??e 2023,\nque la force soit avec vous!"
    # grid.legend = "Que l'ann??e 2023 vous permette de \nsurmonter les obstacles avec r??silience!"
    grid.legend="Belle et joyeuse ann??e 2023!"
    # grid.legend="Belle et heureuse ann??e 2023!"
    print(grid)
    grid.repartitionGraph.divideVertically(0.7)
    grid.repartitionGraph.children[0].divideHorizontally(0.38)
    grid.repartitionGraph.children[0].children[1].divideVertically(0.4)
    grid.repartitionGraph.children[0].children[1].children[1].divideHorizontally(0.6)
    grid.repartitionGraph.children[1].divideHorizontally(0.6)
    print(grid)
    l = grid.loadImages("./carte2023")
    permutation = [3, 0, 1, 5, 4, 2]
    ordered_images = [l[permutation[i]] for i in range(6)]
    transforms = []
    transforms.append([ImageTransform("Move", 0, -0.25)]) # [ImageTransform("Zoom", 1.5)]) # Image 1 
    transforms.append([ImageTransform("Zoom", 1.05), ImageTransform("Move", -0.15, -0.023)]) # Image 2
    transforms.append([ImageTransform("Zoom", 1.7), ImageTransform("Move", -.15, -.355)]) # Image 3
    transforms.append([ImageTransform("Move", 0, -0.15)]) # [ImageTransform("Zoom", 1), ) # Image 4
    transforms.append([ImageTransform("Move", -0.2, 0)]) # Image 5
    transforms.append([ImageTransform("Zoom", 1.1)]) #[ImageTransform("Move", -0.18, 0)]) # Image 6
    for t in transforms:
        t.append(ImageTransform("FixedMargin", int(grid.size_x / 200)))
    grid.repartitionGraph.setImages(ordered_images, transforms)
    print(grid)
    # grid.gen()
    return grid


def main():
    global collage1, collage2, collage3
    # collage1 = collage2023_1()
    # collage2 = collage2023_2()
    collage3 = collage2023_3()
    collage3.saveAsJpegWithLegend("./collage_2023.jpg")

def reload():
    global DivisionGraph, Grid, ImageTransform
    global collage2023_1, collage2023_2, collage2023_3
    del DivisionGraph
    del Grid
    del ImageTransform
    del collage2023_1
    del collage2023_2
    del collage2023_3
    exec(open(sys.argv[0]).read())

# TODO: Add class to handle background transforms.
def isSorted(array):
    return all(a <= b for a, b in zip(array, array[1:]))

# Thanks Stackoverflow
def colorForGradient(percent, colorArray, rangePercentages):
    def getIndex(ranges, x): 
        return (bisect.bisect_left(ranges, x), bisect.bisect_right(ranges, x))
    i0, i1 = getIndex(rangePercentages, percent)
    if i0 == i1:
        # In the middle of an interval
        innerColor = colorArray[i0 - 1]
        outerColor = colorArray[i1]
        p = (rangePercentages[i0] - percent) / (rangePercentages[i0] - rangePercentages[i0 - 1])
    else:
        innerColor = colorArray[i0]
        outerColor = colorArray[i0]
        p = 1
    #Calculate r, g, and b values
    # print(p)
    r = outerColor[0] * (1 - p) + innerColor[0] * p
    g = outerColor[1] * (1 - p) + innerColor[1] * p
    b = outerColor[2] * (1 - p) + innerColor[2] * p
    return (int(r), int(g), int(b))

def genRadialRadient(imageSize, center, colorArray, rangePercentages):
    x0, y0 = center
    longestSemiDiagonal = math.sqrt(2) * max(x0, imageSize[0] - x0, y0, imageSize[1] - y0)
    image = Image.new('RGBA', imageSize)
    assert len(colorArray) == len(rangePercentages)
    assert isSorted(rangePercentages)
    innerColor = [80, 80, 255] # Color at the center
    outerColor = [0, 0, 80] # Color at the corners

    def colorForCoords(x, y):
        # Find the distance to the center
        distanceToCenter = math.sqrt((x - x0) ** 2 + (y - y0) ** 2)
        # Make it on a scale from 0 to 1
        distanceToCenter = float(distanceToCenter) / longestSemiDiagonal
        return colorForGradient(distanceToCenter, colorArray, rangePercentages)

    for y in range(imageSize[1]):
        for x in range(imageSize[0]):
            #Place the pixel        
            image.putpixel((x, y), colorForCoords(x, y))
    return image


main()

# TODO: Add radial gradiant

if False:
    color_1 = hex_to_rgb("000000") # hex_to_rgb("812627")
    color_2 = hex_to_rgb("FF0000") # hex_to_rgb("631D1E")
    color_3 = hex_to_rgb("00FF00") # hex_to_rgb("621D1E")
    color_4 = hex_to_rgb("0000FF") # hex_to_rgb("671E20")
    # im = genRadialRadient((800, 800), (400, 400), [(0, 0, 255), (0, 255, 0)], [0, 1])
    # colors = [color_1, color_2, color_4]
    # ranges = [0, 0.5, 1]
    color_1 = hex_to_rgb("812627")
    color_2 = hex_to_rgb("631D1E")
    color_3 = hex_to_rgb("621D1E")
    color_4 = hex_to_rgb("671E20")
    colors = [color_1, color_2, color_3, color_4]
    ranges = [0, 0.5, 0.9, 1]
    im = genRadialRadient((800, 800), (400, 400), colors, ranges)

    # for i in range(101):
    #     print(i, colorForGradient(float(i)/100., colors, ranges))

