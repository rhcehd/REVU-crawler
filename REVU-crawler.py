import os
import sys
import time
from _winapi import CREATE_NO_WINDOW

from PyQt5 import uic
from PyQt5.QtCore import Qt, QThread
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QTableWidgetItem
from selenium import webdriver
from selenium.common import TimeoutException, ElementClickInterceptedException, StaleElementReferenceException, \
    NoSuchElementException
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

driver: webdriver.Chrome
work_driver: webdriver.Chrome
common_wait: WebDriverWait
search_wait: WebDriverWait
action: ActionChains

COMMON_WAIT_SECONDS = 20
CRAWLER_WAIT_SECONDS = 0
SEARCH_WAIT_SECONDS = 2


class LoginWindow(QMainWindow, uic.loadUiType('src/login.ui')[0]):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(os.path.abspath('src/icon.ico')))
        self.setupUi(self)
        self.login_button.clicked.connect(self.login)

        try:
            global driver, work_driver, common_wait, search_wait, action
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--window-size=1920, 1080')
            options.add_argument('--start-maximized')
            options.add_argument('--blink-settings=imagesEnabled=false')
            service = Service()
            service.creation_flags = CREATE_NO_WINDOW
            driver = webdriver.Chrome(options=options, service=service)
            driver.implicitly_wait(COMMON_WAIT_SECONDS)
            # work_driver = webdriver.Chrome(options=options)
            common_wait = WebDriverWait(driver, COMMON_WAIT_SECONDS)
            search_wait = WebDriverWait(driver, SEARCH_WAIT_SECONDS)
            action = ActionChains(driver)
        except Exception as e:
            QMessageBox.information(self, ' ', e, QMessageBox.Ok, QMessageBox.Ok)

    def login(self):
        if self.login_id.text() == '':
            QMessageBox.information(self, ' ', '아이디 미입력', QMessageBox.Ok, QMessageBox.Ok)
            return None
        if self.login_pw.text() == '':
            QMessageBox.information(self, ' ', '비밀번호 미입력', QMessageBox.Ok, QMessageBox.Ok)
            return None

        user_id = self.login_id.text()
        user_pw = self.login_pw.text()
        driver.get('https://report.revu.net/auth/login')
        driver.find_element(By.XPATH, '//*[@id="app"]/div/div/form/div[1]/input[1]').send_keys(user_id)
        driver.find_element(By.XPATH, '//*[@id="app"]/div/div/form/div[1]/input[2]').send_keys(user_pw)
        driver.find_element(By.XPATH, '//*[@id="app"]/div/div/form/div[3]/button').click()
        modal_close_button = common_wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'guide-close')))
        driver.execute_script('arguments[0].click();', modal_close_button)
        if driver.current_url != 'https://report.revu.net/service/dashboard':
            QMessageBox.information(self, ' ', '로그인 실패', QMessageBox.Ok, QMessageBox.Ok)
        else:
            global window
            window = MainWindow()
            window.show()
            self.close()


class Campaign:
    def __init__(self, number, title):
        self.number = number
        self.title = title


class MainWindow(QMainWindow, uic.loadUiType('src/main.ui')[0]):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowIcon(QIcon(os.path.abspath('src/icon.ico')))
        self.list_widget.itemDoubleClicked.connect(self.list_widget_item_double_clicked)

        self.thread = None
        self.campaigns = []
        self.initialize_data()

    def initialize_data(self):
        self.load_campaign_list()

    def load_campaign_list(self):
        driver.get('https://report.revu.net/service/campaigns')
        campaign_list = common_wait.until(EC.presence_of_element_located(
            (By.XPATH, '//*[@id="app"]/div/div/section[3]/div/div/div/div/div[3]/div/table/tbody'))
        )
        campaign_list = campaign_list.find_elements(By.TAG_NAME, 'tr')
        for campaign in campaign_list:
            number = campaign.find_element(By.XPATH, 'td[1]').text
            title = campaign.find_element(By.XPATH, 'td[2]/div[3]/span').text
            self.campaigns.append(Campaign(number, title))
            self.list_widget.addItem(title)

    def get_campaign_number_by_title(self, title):
        for campaign in self.campaigns:
            if campaign.title == title:
                return campaign.number
        return ''

    def initialize_table_widget(self, row_count=0):
        self.table_widget.clear()
        self.table_widget.setColumnCount(6)
        self.table_widget.setHorizontalHeaderLabels(['이름', '주제', '이웃수', '투데이', '좋아요', '댓글'])
        self.table_widget.setRowCount(row_count)

    def list_widget_item_double_clicked(self):
        self.initialize_table_widget()
        selected_title = self.list_widget.currentItem().text()
        campaign_number = self.get_campaign_number_by_title(selected_title)
        self.thread = WorkThread(self, campaign_number)
        self.thread.start()

    def load_influencer_data_test(self, campaign_number):
        driver.get('https://report.revu.net/service/campaigns/' + campaign_number)

    def load_influencer_data(self, campaign_number):
        driver.get('https://report.revu.net/service/campaigns/' + campaign_number)
        tab_influencer = common_wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'client-pick')))
        tab_influencer.click()
        influencer_list = driver.find_element(By.CLASS_NAME, 'doubleCell')
        total_list_count_string = driver.find_element(By.CLASS_NAME, 'table-title').text.split()[2]
        total_list_count = int(total_list_count_string)
        expected_list_count = 30
        polling_count = 0
        while True:
            try:
                time.sleep(0.2)
                list_count = len(influencer_list.find_elements(By.TAG_NAME, "dl"))
                if list_count == total_list_count:
                    break
                if list_count == expected_list_count or polling_count == 10:
                    expected_list_count += 30
                    polling_count = 0
                    more_button: WebElement
                    more_button = search_wait.until(EC.visibility_of_element_located(
                        (By.XPATH, '//*[@id="pick-list"]/div[3]/span'))
                    )
                    more_button.click()
                polling_count += 1
            except (ElementClickInterceptedException, StaleElementReferenceException):
                # time.sleep(0.05)
                continue
            # except TimeoutException:
            #     break

        influencer_list = influencer_list.find_elements(By.TAG_NAME, "dl")

        item_count = len(influencer_list)
        self.initialize_table_widget(item_count)
        self.progressbar.setMaximum(item_count)
        self.progressbar.setTextVisible(True)

        for i, web_element in enumerate(influencer_list):
            # if i == 30:
            #     break
            try:
                influencer_info = web_element.find_element(By.XPATH, 'dd/div/div[1]')
                temp_name = influencer_info.find_element(By.XPATH, 'div[2]/div[1]').text
                influencer_name = temp_name.replace('\n중복참여', '').replace('\n동시신청', '')

                driver.execute_script("arguments[0].click();", influencer_info)
                driver.switch_to.window(driver.window_handles[1])
                blog_failure_count = 0
                while True:
                    try:
                        if driver.current_url.__contains__("://m."):
                            break
                        blog_addr = driver.current_url.replace('https://', 'https://m.').replace('http://', 'http://m.')
                        driver.get(blog_addr)
                    except Exception as e:
                        print(e)
                        if blog_failure_count == 10:
                            break
                        blog_failure_count += 1

                blogger_info = common_wait.until(EC.presence_of_element_located(
                    (By.XPATH, '//*[@id="root"]/div[4]/div/div[2]/div[2]/div[2]')
                ))
                blog_subject = blogger_info.find_element(By.XPATH, 'span[1]').text.replace('ㆍ', '')
                blog_buddy = blogger_info.find_element(By.XPATH, 'span[2]').text.replace('명의 이웃', '').replace(',', '')
                blog_today = common_wait.until(EC.presence_of_element_located(
                    (By.XPATH, '//*[@id="root"]/div[4]/div/div[1]/div')
                )).text.split(' ')[1].replace(',', '')

                button_show_text_type: WebElement = common_wait.until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="postlist_block"]/div[1]/div/div/button[2]'))
                )
                button_click_count = 0
                while True:
                    if button_click_count == 20:
                        break
                    if button_show_text_type.get_attribute('class').__contains__('active'):
                        break
                    driver.execute_script('arguments[0].click()', button_show_text_type)
                    button_click_count += 1
                    time.sleep(0.1)
                total_like = 0
                total_comment = 0
                driver.implicitly_wait(CRAWLER_WAIT_SECONDS)
                for post_number in range(1, 10):
                    post: WebElement = common_wait.until(
                        EC.visibility_of_element_located(
                            (By.XPATH, '//*[@id="postlist_block"]/div[2]/div/div[2]/ul/div[' + str(post_number) + ']')
                        )
                    )
                    try:
                        like_count = post.find_element(By.XPATH, 'div/a/div[3]/span[1]').text
                    except NoSuchElementException:
                        like_count = 0
                    try:
                        comment_count = post.find_element(By.XPATH, 'div/a/div[3]/span[2]').text
                    except NoSuchElementException:
                        comment_count = 0
                    total_like += int(like_count)
                    total_comment += int(comment_count)
                driver.implicitly_wait(COMMON_WAIT_SECONDS)
                average_like = int(total_like / 10)
                average_comment = int(total_comment / 10)

                item_influencer_name = QTableWidgetItem(influencer_name)
                item_blog_subject = QTableWidgetItem(blog_subject)
                item_blog_buddy = QTableWidgetItem()
                item_blog_today = QTableWidgetItem()
                item_average_like = QTableWidgetItem()
                item_average_comment = QTableWidgetItem()
                item_blog_buddy.setData(Qt.DisplayRole, int(blog_buddy))
                item_blog_today.setData(Qt.DisplayRole, int(blog_today))
                item_average_like.setData(Qt.DisplayRole, average_like)
                item_average_comment.setData(Qt.DisplayRole, average_comment)
                self.table_widget.setItem(i, 0, item_influencer_name)
                self.table_widget.setItem(i, 1, item_blog_subject)
                self.table_widget.setItem(i, 2, item_blog_buddy)
                self.table_widget.setItem(i, 3, item_blog_today)
                self.table_widget.setItem(i, 4, item_average_like)
                self.table_widget.setItem(i, 5, item_average_comment)

                self.progressbar.setValue(i + 1)

                driver.close()
                driver.switch_to.window(driver.window_handles[0])
            except TimeoutException as e:
                print(e)
                self.progressbar.setValue(i + 1)
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                continue
        self.progressbar.setTextVisible(False)
        self.progressbar.setValue(0)


class WorkThread(QThread):
    def __init__(self, work: MainWindow, campaign_number: int):
        super().__init__()
        self.work = work
        self.campaign_number = campaign_number

    def run(self):
        self.work.load_influencer_data(self.campaign_number)


window = None


def main():
    app = QApplication(sys.argv)
    global window
    window = LoginWindow()
    window.show()
    app.exec_()


if __name__ == '__main__':
    main()
