import pydicom
import cv2
import numpy as np
import matplotlib.pyplot as plt

import time
import os

from speckle_tracking import SpeckleTracking
from tools import Cv2Tools

# from mouse_event import

cv2_tool = Cv2Tools()


class Cv2Line():

    def __init__(self, main_window, imgs: np, delta_x: float, delta_y: float, window_name: str,
                 temp_size: int, default_search: int, method: str, draw_delay: int, json_para: dict):

        self.mw = main_window
        self.json_para = json_para

        self.IMGS = imgs
        self.window_name = window_name

        self.current_page = 0
        self.default_search = default_search
        self.temp_size = temp_size

        self.delta_x = delta_x
        self.delta_y = delta_y
        if self.delta_x == 0 or self.delta_y == 0:
            self.delta = np.array([1, 1])
        else:
            self.delta = np.array([self.delta_x, self.delta_y])

        print("The shape of dicom is :", self.IMGS.shape)

        self.IMGS_GRAY = np.asarray([cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) for img in self.IMGS])

        self.img_label = np.copy(self.IMGS)
        self.num_of_img, self.h, self.w = self.IMGS.shape[:3]
        self.num_of_line = 0

        # 畫圖顏色
        self.color_index = 0
        self.num_of_color = self.json_para['line']['color']['amount']
        self.colors = cv2_tool.color_iterater(x=self.num_of_color,
                                              saturation=self.json_para['line']['color']['saturation'],
                                              lightness=self.json_para['line']['color']['lightness'])
        self.current_color = self.colors[self.color_index % self.num_of_color]

        # 讀取 json 中 font 與 line 的參數
        self.font_show = self.json_para['font']['show']
        self.font_size = self.json_para['font']['size']
        self.font_bold = self.json_para['font']['bold']
        self.line_bold = self.json_para['line']['bold']

        # 點相關參數
        self.target_point = []  # -> tuple
        self.track_done = []
        self.search_point = []  # -> list -> tuple
        self.search_shift = []
        self.result_point = {}
        self.result_distance = {}
        self.result_dx = {}
        self.result_dy = {}
        self.result_strain = {}

        # 顯示
        # cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, self.mw.w, self.mw.h)
        cv2.createTrackbar('No', self.window_name, 0, self.num_of_img - 1, self.track_change)
        cv2.imshow(self.window_name, self.img_label[self.current_page])
        cv2.waitKey(1)

        self.speckle_tracking = SpeckleTracking(method=method)

    # 重置所有動作
    def reset(self):
        self.img_label = np.copy(self.IMGS)
        cv2.imshow(self.window_name, self.img_label[self.current_page])

        self.num_of_line = 0
        self.color_index = 0
        self.current_color = self.colors[self.color_index % self.num_of_color]
        self.target_point = []
        self.track_done = []
        self.search_point = []
        self.search_shift = []
        self.result_point = {}
        self.result_distance = {}
        self.result_dx = {}
        self.result_dy = {}
        self.result_strain = {}

        print('Reseting complete.')

    # track bar 更動
    def track_change(self, x: int):
        '''
        Track bar 變動時的呼叫函數
        :param x: 變動後的值
        :return: None
        '''
        self.current_page = x
        cv2.imshow(self.window_name, self.img_label[self.current_page])

    # 滑鼠事件
    def click_event(self, event, x, y, flags, param):

        # 滾輪選擇照片
        if event == cv2.EVENT_MOUSEWHEEL:
            if flags < 0:
                self.current_page = cv2_tool.photo_switch('next', self.current_page, self.num_of_img)
            elif flags > 0:
                self.current_page = cv2_tool.photo_switch('last', self.current_page, self.num_of_img)

            # 更新 Trackbar，__track_change會更新圖片
            cv2.setTrackbarPos('No', self.window_name, self.current_page)

        # 劃出線段（左鍵點擊時）
        if event == cv2.EVENT_LBUTTONDOWN:
            self.mouse_drag = False
            self.point1 = (x, y)  # 記錄起點

        # 預覽線段（左鍵拖曳時）
        elif flags == 1 & cv2.EVENT_FLAG_LBUTTON:
            self.mouse_drag = True

            # 複製目前畫面，在放開滑鼠之前都在複製畫面上作圖，否則會有許多線段互相覆蓋
            temp_img = np.copy(self.img_label[self.current_page])
            # print(self.current_color)
            cv2.line(temp_img, self.point1, (x, y), self.current_color, thickness=self.line_bold)

            # 計算距離、顯示距離的座標
            text_point, d, dx, dy = cv2_tool.count_distance(self.point1, (x, y), self.delta)
            font = cv2.FONT_HERSHEY_SIMPLEX
            if self.font_show:
                cv2.putText(temp_img, '{:4.3f}{}'.format(d, '(p)' if self.delta_x == 0 else ''), text_point, font,
                            self.font_size, (255, 255, 255), self.font_bold)

            # 刷新畫面
            cv2.imshow(self.window_name, temp_img)

        # 確定線段（左鍵放開時）
        elif event == cv2.EVENT_LBUTTONUP:
            if self.mouse_drag:
                self.mouse_drag = False  # 拖曳重置

                # 紀錄 point2 的點
                self.point2 = (x, y)

                # 作圖
                cv2.line(self.img_label[self.current_page], self.point1, self.point2, self.current_color,
                         thickness=self.line_bold)
                cv2.circle(self.img_label[self.current_page], self.point1, 0, self.current_color, thickness=2)
                cv2.circle(self.img_label[self.current_page], self.point2, 0, self.current_color, thickness=2)

                # 計算距離 -> 尚未加入 List
                text_point, d, dx, dy = cv2_tool.count_distance(self.point1, self.point2, self.delta)
                font = cv2.FONT_HERSHEY_SIMPLEX
                if self.font_show:
                    cv2.putText(self.img_label[self.current_page],
                                '{:4.3f}{}'.format(d, '(p)' if self.delta_x == 0 else ''),
                                text_point, font, self.font_size, (255, 255, 255), self.font_bold)

                # 新增點參數
                self.target_point.extend([self.point1, self.point2])
                self.track_done.extend([False, False])

                # 計算預設的 search window
                x, y = self.point1
                s11, s12, _, _ = cv2_tool.get_search_window((x, y), (
                x + self.default_search // 2, y + self.default_search // 2), self.temp_size)
                x, y = self.point2
                s21, s22, _, _ = cv2_tool.get_search_window((x, y), (
                x + self.default_search // 2, y + self.default_search // 2), self.temp_size)

                self.search_point.extend([[s11, s12], [s21, s22]])
                self.search_shift.extend([(self.default_search // 2, self.default_search // 2),
                                          (self.default_search // 2, self.default_search // 2)])

                print(f"{self.point1}, {self.point2}")

                cv2.imshow(self.window_name, self.img_label[self.current_page])

                # 先將第一點的距離輸入結果
                self.result_distance[self.color_index] = [d]
                self.result_dx[self.color_index] = [dx]
                self.result_dy[self.color_index] = [dy]

                # 更新顏色
                self.color_index += 1
                self.current_color = self.colors[self.color_index % self.num_of_color]

                # 更新座標
                points_show = self.mw.textBrowser_labeled_points.toPlainText()
                if self.mw.scaling == 100:
                   points_show += f"{self.point1}, {self.point2},\n"
                else:
                    points_show += f"{((self.point1[0] * 100 // self.mw.scaling), (self.point1[1] * 100 // self.mw.scaling))}, " \
                                   f"{((self.point2[0] * 100 // self.mw.scaling), (self.point2[1] * 100 // self.mw.scaling))},\n"

                self.mw.textBrowser_labeled_points.setText(points_show)

        # 設定 Search Window（右鍵點擊時）
        if event == cv2.EVENT_RBUTTONDOWN:
            self.mouse_drag = False
            # 計算點擊位置與各點之間的距離
            target = np.asarray(self.target_point)
            diff = target - np.asarray([x, y])
            # 距離最近者為此次框 ROI 的點
            self.t_point_index = np.argmin(np.sum(np.square(diff), axis=1))
            self.t_point = self.target_point[self.t_point_index]


        # 畫 Search Window 範圍（右鍵拖曳時）
        elif flags == 2 & cv2.EVENT_FLAG_RBUTTON:
            self.mouse_drag = True

            # 複製框圖模板
            temp_img = np.copy(self.img_label[self.current_page])

            # 計算 Search Winodw, Calculate Range
            s1, s2, c1, c2 = cv2_tool.get_search_window(self.t_point, (x, y), self.temp_size)

            cv2.rectangle(temp_img, s1, s2, (255, 0, 0), thickness=1)
            cv2.rectangle(temp_img, c1, c2, (255, 255, 0), thickness=1)

            # 更新圖片
            cv2.imshow(self.window_name, temp_img)


        # 確定 Search Window 範圍（右鍵放開時）
        elif event == cv2.EVENT_RBUTTONUP:
            if self.mouse_drag:
                self.mouse_drag = False  # 拖曳重置

                tx, ty = self.t_point

                # 計算 Search Winodw, Calculate Range
                s1, s2, c1, c2 = cv2_tool.get_search_window((tx, ty), (x, y), self.temp_size)

                # 紀錄範圍
                self.search_point[self.t_point_index] = [s1, s2]
                self.search_shift[self.t_point_index] = (abs(x - tx), abs(y - ty))

                # 畫圖
                cv2.rectangle(self.img_label[self.current_page], s1, s2, (0, 0, 255), thickness=1)
                cv2.rectangle(self.img_label[self.current_page], c1, c2, (255, 255, 0), thickness=1)

                # 更新圖片
                cv2.imshow(self.window_name, self.img_label[self.current_page])

    # 測試時方便建立線段
    def addPoint(self, point1, point2):
        # 作圖
        cv2.line(self.img_label[self.current_page], point1, point2, self.current_color, thickness=self.line_bold)
        cv2.circle(self.img_label[self.current_page], point1, 2, self.current_color, thickness=-1)
        cv2.circle(self.img_label[self.current_page], point2, 2, self.current_color, thickness=-1)

        # 計算距離 -> 尚未加入 List TODO
        text_point, d, dx, dy = cv2_tool.count_distance(point1, point2, self.delta)
        font = cv2.FONT_HERSHEY_SIMPLEX
        if self.font_show:
            cv2.putText(self.img_label[self.current_page], '{:4.3f}{}'.format(d, '(p)' if self.delta_x == 0 else ''),
                        text_point, font, self.font_size, (255, 255, 255), self.font_bold)

        # 新增點參數
        self.target_point.extend([point1, point2])
        self.track_done.extend([False, False])

        x, y = point1
        s11, s12, _, _ = cv2_tool.get_search_window((x, y),
                                                    (x + self.default_search // 2, y + self.default_search // 2),
                                                    self.temp_size)
        x, y = point2
        s21, s22, _, _ = cv2_tool.get_search_window((x, y),
                                                    (x + self.default_search // 2, y + self.default_search // 2),
                                                    self.temp_size)

        self.search_point.extend([[s11, s12], [s21, s22]])
        self.search_shift.extend([(self.default_search // 2, self.default_search // 2),
                                  (self.default_search // 2, self.default_search // 2)])

        cv2.imshow(self.window_name, self.img_label[self.current_page])

        # 先將第一點的距離輸入結果
        self.result_distance[self.color_index] = [d]
        self.result_dx[self.color_index] = [dx]
        self.result_dy[self.color_index] = [dy]

        self.color_index += 1
        self.current_color = self.colors[self.color_index]

    # 畫線的 Speckle Tracking
    def tracking(self, show=False):
        finish_already = True

        progress_denominator = (len(self.track_done) - np.sum(np.asarray(self.track_done))) * (len(self.IMGS) - 1)
        progress_fraction = 0
        for j, (tp, s_shift, done) in enumerate(zip(self.target_point, self.search_shift, self.track_done)):

            # 如果該點完成，跳過該點
            if done: continue

            if j % 2 == 1: self.num_of_line += 1  # 更新 計算機分線條的上限

            finish_already = False
            self.track_done[j] = True
            self.result_point[j] = [tp]

            color = self.colors[(j // 2) % self.num_of_color]

            print('Now is tracking point{}/{}.'.format(j + 1, len(self.target_point)))

            result = tp

            # 從圖1開始抓出，當作 Candidate
            for i in range(1, self.num_of_img):
                progress_fraction += 1
                # target, img1, img2, search_shift, temp_size
                result = self.speckle_tracking.method(result, self.IMGS_GRAY[i - 1], self.IMGS_GRAY[i], s_shift,
                                                      self.temp_size)

                self.result_point[j].append(result)

                cv2.circle(self.img_label[i], result, 2, color, thickness=-1)

                # 若運算的點為直線的第二端，開始畫線
                if j % 2 == 1:

                    # 抓出前次結果的點
                    p_last = self.result_point[j - 1][i]

                    # 畫線、計算（顯示）距離
                    cv2.line(self.img_label[i], p_last, result, color, thickness=self.line_bold)
                    text_point, d, dx, dy = cv2_tool.count_distance(p_last, result, self.delta)
                    if self.font_show:
                        cv2.putText(self.img_label[i], '{:4.3f}{}'.format(d, '(p)' if self.delta_x == 0 else ''),
                                    text_point,
                                    cv2.FONT_HERSHEY_SIMPLEX, self.font_size, (255, 255, 255), self.font_bold)
                    self.result_distance[j // 2].append(d)
                    self.result_dx[j // 2].append(dx)
                    self.result_dy[j // 2].append(dy)

                if show:
                    self.show_progress_bar(self.img_label[i], progress_fraction, progress_denominator)

            self.show_progress_bar(np.copy(self.img_label[0]), progress_fraction, progress_denominator, pos='top')

        cv2.imshow(self.window_name, self.img_label[0])
        cv2.waitKey(1)

        for i in self.result_distance.keys():
            d_list = np.asarray(self.result_distance[i])
            self.result_strain[i] = list((d_list - d_list[0]) / d_list[0])

    def show_progress_bar(self, img, fraction, denominator, pos='down'):
        if pos == 'down':
            temp_img = cv2.line(np.copy(img), (0, self.h - 1), (((self.w - 1) * fraction) // denominator, self.h - 1),
                            (216, 202, 28), 5)
        elif pos == 'top':
            temp_img = cv2.line(np.copy(img), (0, 0), (((self.w - 1) * fraction) // denominator, 0),
                                (216, 202, 28), 5)
        cv2.imshow(self.window_name, temp_img)
        cv2.waitKey(1)


class Cv2Point():

    def __init__(self, main_window, imgs: np, delta_x: float, delta_y: float, window_name: str,
                 temp_size: int, default_search: int, method: str, draw_delay: int, json_para: dict):

        self.IMGS = imgs
        self.window_name = window_name
        self.mw = main_window

        self.current_page = 0
        self.default_search = default_search
        self.temp_size = temp_size
        self.draw_delay = draw_delay
        self.draw_count = 0

        self.delta_x = delta_x
        self.delta_y = delta_y
        self.delta = np.array([self.delta_x, self.delta_y])

        print("The shape of dicom is :", self.IMGS.shape)

        self.IMGS_GRAY = np.asarray([cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) for img in self.IMGS])

        self.img_label = np.copy(self.IMGS)
        self.num_of_img, self.h, self.w, _ = self.IMGS.shape

        # 點相關參數
        self.target_point = []  # -> tuple
        self.track_done = []
        self.result_point = {}

        # 顯示
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, self.mw.w, self.mw.h)
        cv2.createTrackbar('No', self.window_name, 0, self.num_of_img - 1, self.track_change)
        cv2.imshow(self.window_name, self.img_label[self.current_page])
        cv2.waitKey(1)

        self.speckle_tracking = SpeckleTracking(method=method)

    # 重置所有動作
    def reset(self):
        self.img_label = np.copy(self.IMGS)
        cv2.imshow(self.window_name, self.img_label[self.current_page])

        self.target_point = []
        self.track_done = []
        self.search_point = []
        self.search_shift = []
        self.result_point = {}

        print('Reseting complete.')

    # track bar 更動
    def track_change(self, x: int):
        '''
        Track bar 變動時的呼叫函數
        :param x: 變動後的值
        :return: None
        '''
        self.current_page = x
        cv2.imshow(self.window_name, self.img_label[self.current_page])

    def draw_point(self, x, y):
        if (x, y) not in self.target_point:
            self.target_point.append((x, y))
            self.track_done.append(False)
            cv2.circle(self.img_label[self.current_page], (x, y), 1, (0, 0, 255), -1)

            # 刷新畫面
            cv2.imshow(self.window_name, self.img_label[self.current_page])
            cv2.waitKey(1)

    # 滑鼠事件
    def click_event(self, event, x, y, flags, param):

        # 滾輪選擇照片
        if event == cv2.EVENT_MOUSEWHEEL:
            if flags < 0:
                self.current_page = cv2_tool.photo_switch('next', self.current_page, self.num_of_img)
            elif flags > 0:
                self.current_page = cv2_tool.photo_switch('last', self.current_page, self.num_of_img)

            # 更新 Trackbar，__track_change會更新圖片
            cv2.setTrackbarPos('No', self.window_name, self.current_page)

        # 劃出線段（左鍵點擊時）
        if event == cv2.EVENT_LBUTTONDOWN:
            self.draw_point(x, y)
            self.draw_count += 1

        # 預覽線段（左鍵拖曳時）
        elif flags == 1 & cv2.EVENT_FLAG_LBUTTON:
            if self.draw_count % self.draw_delay == 0:
                self.draw_point(x, y)
            self.draw_count += 1

        # 確定線段（左鍵放開時）
        elif event == cv2.EVENT_LBUTTONUP:
            self.draw_point(x, y)
            self.draw_count = 0

        # 設定 Search Window（右鍵點擊時）
        if event == cv2.EVENT_RBUTTONDOWN:
            pass

        # 畫 Search Window 範圍（右鍵拖曳時）
        elif flags == 2 & cv2.EVENT_FLAG_RBUTTON:
            pass

        # 確定 Search Window 範圍（右鍵放開時）
        elif event == cv2.EVENT_RBUTTONUP:
            pass

    # 測試時方便建立線段
    def addPoint(self, point):
        self.target_point.append(point)
        self.track_done.append(False)

        # 作圖
        cv2.circle(self.img_label[self.current_page], point, 1, (0, 0, 255), thickness=-1)
        cv2.imshow(self.window_name, self.img_label[self.current_page])
        cv2.waitKey(1)

    # 畫線的 Speckle Tracking
    def tracking(self, show=False):
        finish_already = True
        search_shift = (self.default_search // 2, self.default_search // 2)

        progress_denominator = (len(self.track_done) - np.sum(np.asarray(self.track_done))) * (len(self.IMGS) - 1)
        progress_fraction = 0
        for j, (tp, done) in enumerate(zip(self.target_point, self.track_done)):

            # 如果該點完成，跳過該點
            if done: continue

            finish_already = False
            self.track_done[j] = True
            self.result_point[j] = [tp]

            print('Now is tracking point{}/{}.'.format(j + 1, len(self.target_point)))

            result = tp

            # 從圖1開始抓出，當作 Candidate
            for i in range(1, self.num_of_img):
                progress_fraction += 1
                # target, img1, img2, search_shift, temp_size
                result = self.speckle_tracking.method(result, self.IMGS_GRAY[i - 1], self.IMGS_GRAY[i], search_shift,
                                                      self.temp_size)
                self.result_point[j].append(result)
                cv2.circle(self.img_label[i], result, 1, (0, 0, 255), thickness=-1)

                if show:
                    # 進度條模式顯示
                    self.show_progress_bar(self.img_label[i], progress_fraction, progress_denominator)

            self.show_progress_bar(np.copy(self.img_label[0]), progress_fraction, progress_denominator, pos='top')

        cv2.imshow(self.window_name, self.img_label[0])
        cv2.waitKey(1)

    def show_progress_bar(self, img, fraction, denominator, pos='down'):
        if pos == 'down':
            temp_img = cv2.line(np.copy(img), (0, self.h - 1), (((self.w - 1) * fraction) // denominator, self.h - 1),
                            (216, 202, 28), 5)
        elif pos == 'top':
            temp_img = cv2.line(np.copy(img), (0, 0), (((self.w - 1) * fraction) // denominator, 0),
                                (216, 202, 28), 5)
        cv2.imshow(self.window_name, temp_img)
        cv2.waitKey(1)


class SetDelta():
    def __init__(self, img):
        self.img = img
        h, w = img.shape[:2]
        self.window_name = 'Set delta'
        self.undo = True
        cv2.namedWindow(self.window_name, 0)
        cv2.resizeWindow(self.window_name, w, h)
        cv2.imshow(self.window_name, self.img)
        cv2.waitKey(1)

    # 滑鼠事件
    def click_event(self, event, x, y, flags, param):

        # 劃出線段（左鍵點擊時）
        if event == cv2.EVENT_LBUTTONDOWN:
            self.mouse_drag = False
            self.point1 = (x, y)  # 記錄起點

        # 預覽線段（左鍵拖曳時）
        elif flags == 1 & cv2.EVENT_FLAG_LBUTTON:
            self.mouse_drag = True

            # 複製目前畫面，在放開滑鼠之前都在複製畫面上作圖，否則會有許多線段互相覆蓋
            temp_img = np.copy(self.img)
            # print(self.current_color)
            cv2.line(temp_img, self.point1, (x, y), (0, 0, 255), thickness=1)

            # 刷新畫面
            cv2.imshow(self.window_name, temp_img)

        # 確定線段（左鍵放開時）
        elif event == cv2.EVENT_LBUTTONUP:
            if self.mouse_drag:
                self.mouse_drag = False  # 拖曳重置

                temp_img = np.copy(self.img)

                # 紀錄 point2 的點
                self.point2 = (x, y)

                cv2.line(temp_img, self.point1, self.point2, (0, 0, 255), thickness=1)
                cv2.circle(temp_img, self.point1, 1, (0, 0, 255), thickness=2)
                cv2.circle(temp_img, self.point2, 1, (0, 0, 255), thickness=2)

                cv2.imshow(self.window_name, temp_img)

                self.undo = False






if __name__ == '__main__':
    pass
