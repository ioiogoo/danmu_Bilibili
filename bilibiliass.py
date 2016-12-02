# *-* coding:utf-8 *-*
import re
import math
import codecs
import requests

'''
弹幕类型:
        1: 普通滚动
        4: 底部中间
        5: 顶部中间
默认设置项：
        分辨率：1024*768
        行数：12
        滚动弹幕时间：5s
        静止弹幕时间：2s
        透明度：0.8
'''
WIDTH = 1024                         # 宽度
HEIGHT = 768                         # 高度
ROWS = 12                            # 行数
SIZE = WIDTH/(ROWS+8)                # 字体大小
DURATION_D = 6                       # 滚动弹幕持续时间
DURATION_S = 2                       # 静止弹幕持续时间
ALPHA = 0.8                          # 透明度

ScriptInfo = \
'''[Script Info]
Title: Default Aegisub file
Author: ioiogoo
Original Script: 哔哩哔哩 - ( ゜- ゜)つロ 乾杯~
ScriptType: v4.00+
Collisions: Normal
PlayResX: %s
PlayResY: %s
''' % (WIDTH, HEIGHT)

Styles = \
'''[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Dedualt,微软雅黑,%(Fontsize)d,&H%(alpha)02XFFFFFF,&H%(alpha)02XFFFFFF,&H%(alpha)02X000000,&H%(alpha)02X000000,0,0,0,0,100,100,0.00,0.00,1,1.00,0.00,2,30,30,30,0
''' % {'Fontsize': SIZE, 'alpha': 255-round(ALPHA*255)}

Events = \
'''[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''

class Bilizimu(object):

##############################################################################
## 整体流程为：                                                             ##
## 判断输入的是文件名还是av代号                                             ##
## WriteFile将ConvertComment生成的ass字幕格式写入文件                       ##
## ConvertComment调用ComposeComment生成的单个list生成单行字幕格式           ##
## ComposeComment调用ReadComment生成的单行弹幕内容                          ##
##############################################################################

    def __init__(self, inputcontent):
        self.re_c = re.compile(r'<d\sp="([\d\.]+),([145]),(\d+),(\d+),\d+,\d+,\w+,\d+">([^<>]+?)</d>')
        self.inputcontent = inputcontent
        self.baseavurl = 'http://www.bilibili.com/video/'
        self.basecomurl = 'http://comment.bilibili.com/%d.xml'

    def Genera_ass(self):
        if re.match(r'av\d+', self.inputcontent):
            outputfile = self.inputcontent
            inputcontent = requests.get(self.baseavurl+self.inputcontent).content
            cid = re.findall(r'cid=(\d+)', inputcontent)[0]
            inputcontent = requests.get(self.basecomurl%int(cid)).content
        else:
            outputfile = re.findall('(.+?)\.xml', self.inputcontent)[0]
            inputcontent = self.inputcontent

        self.WriteFile(inputcontent, outputfile)

    def ReadComment(self, filename):
        '''生成器，一行一行输出内容'''
        # 判断是输入的文件名还是xml代码
        if re.match(r'.+?\.xml', filename):
            with open(filename) as f:
                for line in f:
                    if self.re_c.findall(line):
                        # 格式为：(出现时间，字幕类型， 字体大小， 颜色， 内容)
                        yield self.re_c.findall(line)[0]
        else:
            for line in self.re_c.findall(filename, re.S):
                yield line


    def ComposeComment(self, filename):
        '''
        组合弹幕，将不同类型的弹幕放到一个list
        并且当list存满ROWS时输出给ConvertComment
        '''
        rows = [[] for i in xrange(3)]
        # 弹幕类型
        category_dic = {'1':0, '4':1, '5':2}
        for index, comment in enumerate(self.ReadComment(filename), 1):
            category = category_dic[comment[1]]
            rows[category].append(comment)
            if len(rows[category]) == ROWS:
                yield rows[category]
                rows[category] = []
        for row in rows:
            yield row



    def ConvertComment(self, rows):
        '''接受一个list为输入，转换成规则的ass字幕格式'''
        ass_format = 'Dialogue: 1,%(start)s,%(end)s,Dedualt,,0000,0000,0000,,{%(styles)s}%(text)s\n'
        for index, comment in enumerate(rows, 1):
            if not comment:continue
            timestamp = float(comment[0])
            text = comment[4]
            styles = []
            if comment[1] == '1':
                styles.append('\\move(%(width)d, %(row)d, %(neglen)d, %(row)d)' % {'width': WIDTH, 'row': index*SIZE, 'neglen': -math.ceil(len(text)*SIZE)})
                duration = DURATION_D
            if comment[1] == '5':
                styles.append('\\an8\\pos(%(halfwidth)d, %(row)d)' % {'halfwidth': WIDTH/2, 'row': SIZE*index})
                duration = DURATION_S
            if comment[1] == '4':
                styles.append('\\an8\\pos(%(halfwidth)d, %(row)d)' % {'halfwidth': WIDTH/2, 'row': (HEIGHT - (SIZE + 10)*index)})
                duration = DURATION_S
            if int(comment[3]) != 0xffffff:
                styles.append('\\c&H%s&' % self.ConvertColor(int(comment[3])))
            if int(comment[3]) == 0x000000:
                styles.append('\\3c&HFFFFFF&')
            start = self.ConvertTimestamp(timestamp)
            end = self.ConvertTimestamp(timestamp+duration)
            yield ass_format % {'start':start, 'end':end, 'styles': ''.join(styles), 'text':text}


    def ConvertTimestamp(self, timestamp):
        '''转换xml里面的时间戳为标准时间格式'''
        timestamp = round(timestamp*100.0)
        hour, minute = divmod(timestamp, 360000)
        minute, second = divmod(minute, 6000)
        second, centsecond = divmod(second, 100)
        return '%d:%02d:%02d.%02d' % (int(hour), int(minute), int(second), int(centsecond))

    def ConvertColor(self, RGB, width=1280, height=576):
        '''转换xml里面的颜色为ass格式的颜色'''
        if RGB == 0x000000:
            return '000000'
        elif RGB == 0xffffff:
            return 'FFFFFF'
        R = (RGB >> 16) & 0xff
        G = (RGB >> 8) & 0xff
        B = RGB & 0xff
        if width < 1280 and height < 576:
            return '%02X%02X%02X' % (B, G, R)
        else:  # VobSub always uses BT.601 colorspace, convert to BT.709
            ClipByte = lambda x: 255 if x > 255 else 0 if x < 0 else round(x)
            return '%02X%02X%02X' % (
                ClipByte(R*0.00956384088080656+G*0.03217254540203729+B*0.95826361371715607),
                ClipByte(R*-0.10493933142075390+G*1.17231478191855154+B*-0.06737545049779757),
                ClipByte(R*0.91348912373987645+G*0.07858536372532510+B*0.00792551253479842)
            )

    def WriteFile(self, inputfile, outputfile='bilibili'):
         with codecs.open(outputfile+'.ass', 'a', 'utf_8_sig') as f:
            f.write(ScriptInfo.decode('utf-8')+'\n\n')
            f.write(Styles.decode('utf-8')+'\n\n')
            f.write(Events.decode('utf-8'))
            rows_gen = self.ComposeComment(inputfile)
            for row in rows_gen:
                ass_gen = self.ConvertComment(row)
                for ass_str in ass_gen:
                    f.write(ass_str.decode('utf-8'))

if __name__ == '__main__':
    Bilizimu('av2271112').Genera_ass()

