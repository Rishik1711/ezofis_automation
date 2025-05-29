from collections.abc import KeysView
import pytest
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import psutil
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global driver instance
_driver = None

def get_driver():
    """Get or create Chrome driver instance"""
    global _driver
    if _driver is None:
        try:
            logger.info("Initializing Chrome driver...")
            chrome_options = Options()
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--window-position=0,0")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_experimental_option("detach", True)  # Keep browser open after script ends
            
            # Get the correct ChromeDriver path
            driver_path = ChromeDriverManager().install()
            # Fix the path to use the actual chromedriver.exe
            if "THIRD_PARTY_NOTICES" in driver_path:
                driver_path = driver_path.replace("THIRD_PARTY_NOTICES.chromedriver", "chromedriver.exe")
            logger.info(f"ChromeDriver path: {driver_path}")
            
            service = Service(executable_path=driver_path)
            _driver = webdriver.Chrome(service=service, options=chrome_options)
            _driver.maximize_window()
            logger.info("Chrome driver initialized successfully")
            
        except Exception as e:
            logger.error(f"Error creating Chrome driver: {e}")
            if _driver:
                try:
                    _driver.quit()
                except:
                    pass
            _driver = None
            raise
            
    return _driver

# Add pytest configuration for ordering
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "order: mark test to set execution order"
    )

@pytest.fixture(scope="session")
def driver():
    """Pytest fixture for browser instance"""
    try:
        driver = get_driver()
        yield driver
    finally:
        # Don't quit the driver automatically
        pass

def focus_browser():
    """Focus the Chrome browser window"""
    if _driver:
        try:
            _driver.set_window_position(0, 0)
            _driver.set_window_size(1920, 1080)
            _driver.execute_script("window.focus();")
        except Exception as e:
            logger.warning(f"Could not focus browser: {e}")

@pytest.mark.order(1)
def test_login_valid_credentials(driver: WebDriver):
    """Test login with valid credentials"""
    print("🔐 Logging in with valid credentials...")
    # Get URL from environment variable
    url = os.environ.get('TEST_URL', 'https://trial.ezofis.com/')
    driver.get(url)
    
    wait = WebDriverWait(driver, 10)
    # Get the email selected from the form
    selected_email = os.environ.get('TEST_EMAIL')
    
    if not selected_email:
        pytest.fail("No email provided for login test")
    
    print(f"📧 Attempting login with email: {selected_email}")
    
    # Wait for and fill in the email field
    email_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='text']")))
    email_field.clear()  # Clear any existing value
    email_field.send_keys(selected_email)
    
    # Rest of the login process
    password_field = driver.find_element(By.XPATH, "//input[@type='password']")
    password_field.send_keys("Ezofis@123")

    signin_button = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, ".sign-in-btn.text-white.bg-primary.shadow-2")
    ))
    signin_button.click()
    
    # Verify successful login
    wait.until(EC.url_contains("/workflows/inbox"))
    assert "/workflows/inbox" in driver.current_url, "Login failed - not redirected to workflows inbox"

@pytest.mark.order(2)
def test_click_task_flow(driver: WebDriver):
    """Test navigating to Task Flow section"""
    print("🧭 Navigating to 'Task Flow' section...")
    task_flow = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Task Flow') and contains(@class, 'text-weight-normal')]"))
    )
    driver.execute_script("arguments[0].scrollIntoView(true);", task_flow)
    time.sleep(1)
    ActionChains(driver).move_to_element(task_flow).click().perform()
    assert task_flow.is_displayed()

@pytest.mark.order(3)
def test_click_initiate(driver: WebDriver):
    """Test clicking initiate button"""
    print("🚀 Clicking on 'Initiate' to start a new task flow...")
    wait = WebDriverWait(driver, 20)
    dynamic_initiate_btn = WebDriverWait(driver, 30).until(
        EC.element_to_be_clickable((By.XPATH, "//div[contains(@class,'q-chip__content') and normalize-space(text())='Initiate']"))
    )
    driver.execute_script("arguments[0].scrollIntoView(true);", dynamic_initiate_btn)
    time.sleep(1)
    ActionChains(driver).move_to_element(dynamic_initiate_btn).click().perform()
    task_form_title = wait.until(
        EC.visibility_of_element_located((By.XPATH, "//div[contains(@class, 'title') and text()='Task Form']"))
    )
    assert task_form_title is not None, "Task Form title not found"

@pytest.mark.order(4)
def test_task_name_enter(driver: WebDriver):
    """Test entering task name"""
    print("📝 Entering the task name as 'Testing Task'...")
    task_name_field = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, "//div[@id='field-label']/div[contains(text(),'Task Name')]/../../following-sibling::div//textarea"))
    )
    driver.execute_script("arguments[0].scrollIntoView(true);", task_name_field)
    time.sleep(1)
    task_name_field.clear()
    task_name_field.send_keys("Testing Task")
    assert task_name_field.get_attribute("value") == "Testing Task", "Task name input failed"

@pytest.mark.order(5)
def test_date_enter(driver: WebDriver):
    """Test entering start date"""
    print("📅 Entering the task start date as '2025-04-05'...")
    start_date_input = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, "(//input[@placeholder='YYYY-MM-DD'])[1]"))
    )
    driver.execute_script("arguments[0].scrollIntoView(true);", start_date_input)
    time.sleep(1)    
    start_date_input.click()
    start_date_input.clear()
    start_date_input.send_keys("2025-04-05")
    assert start_date_input.get_attribute("value") == "2025-04-05", "Start date input failed"

@pytest.mark.order(6)
def test_deadline_enter(driver: WebDriver):
    """Test entering deadline"""
    print("⏰ Setting the task deadline to '2025-04-10'...")
    deadline_input = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, "//div[@id='field-label']/div[contains(text(),'Deadline for the task')]/ancestor::div[@id='date-field']//input[@placeholder='YYYY-MM-DD']"))
    )
    driver.execute_script("arguments[0].scrollIntoView(true);", deadline_input)
    time.sleep(1)
    deadline_input.click()
    deadline_input.clear()
    deadline_input.send_keys("2025-04-10")
    assert deadline_input.get_attribute("value") == "2025-04-10", "Deadline input failed"

@pytest.mark.order(7)
def test_task_type(driver: WebDriver):
    """Test selecting task type"""
    print("📂 Selecting 'Bug Fixing' as the task type...")
    task_type_input = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, "//input[@type='text' and @placeholder='Select']"))
    )
    driver.execute_script("arguments[0].scrollIntoView(true);", task_type_input)
    time.sleep(1)
    task_type_input.click()
    task_type_input.clear()
    task_type_input.send_keys("Bug Fixing")
    time.sleep(1)
    task_type_input.send_keys(Keys.ENTER)

@pytest.mark.order(8)
def test_file_upload(driver: WebDriver):
    """Test file upload"""
    print("📎 Uploading file: 'sample-1.pdf'...")
    divider = driver.find_element(By.ID, "divider")
    ActionChains(driver).move_to_element(divider).click().perform()
    dropdown_closed = WebDriverWait(driver, 5).until(
        EC.invisibility_of_element_located((By.XPATH, "//div[contains(@class,'q-menu')]"))
    )
    assert dropdown_closed, "Dropdown did not close after selection"

    file_input = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, "//input[@type='file' and @multiple='multiple']"))
    )
    driver.execute_script("arguments[0].style.display = 'block';", file_input)
    file_input.send_keys(r"C:\Users\ADMIN\Downloads\sample-1.pdf")
    driver.execute_script("arguments[0].dispatchEvent(new Event('change'))", file_input)
    file_uploaded = WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class, 'uploaded') or contains(text(), 'sample-1.pdf')]"))
    )
    assert any("sample-1.pdf" in el.text for el in file_uploaded), "File upload confirmation not found"

@pytest.mark.order(9)
def test_task_progress(driver: WebDriver):
    """Test setting task progress"""
    print("📊 Setting task progress to 75%...")
    progress_input = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//input[@type='number']"))
    )
    driver.execute_script("arguments[0].scrollIntoView(true);", progress_input)
    ActionChains(driver).move_to_element(progress_input).click().pause(0.5).send_keys("75").perform()
    assert progress_input.get_attribute("value") == "75", "Task progress input value not set correctly"

@pytest.mark.order(10)
def test_update_time(driver: WebDriver):
    """Test updating time"""
    print("⏱️ Updating task time to '10:30 AM'...")
    time_input = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, "//input[@placeholder='HH:MM AA']"))
    )
    driver.execute_script("arguments[0].scrollIntoView(true);", time_input)
    time.sleep(1)
    time_input.click()
    time_input.clear()
    time_input.send_keys("10:30 AM")
    assert time_input.get_attribute("value") == "10:30 AM", "Time input value not set correctly"

@pytest.mark.order(11)
def test_remarks(driver: WebDriver):
    """Test adding remarks"""
    print("💬 Adding remarks: 'Issues noted on trial server'...")
    remarks_field = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, "//div[@id='field-label']/div[contains(text(),'Remarks/Comments')]/../../following-sibling::div//textarea"))
    )
    driver.execute_script("arguments[0].scrollIntoView(true);", remarks_field)
    time.sleep(1)
    remarks_field.clear()
    remarks_field.send_keys("Issues noted on trial server")
    assert remarks_field.get_attribute("value") == "Issues noted on trial server", "Remarks input value not set correctly"

@pytest.mark.order(12)
def test_submit(driver: WebDriver):
    """Test submitting the form"""
    print("✅ Submitting the completed task form...")
    submit_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[.//div[text()='Submit']]"))
    )
    driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
    driver.execute_script("arguments[0].click();", submit_button)
    form_closed = WebDriverWait(driver, 10).until(
        EC.invisibility_of_element_located((By.CLASS_NAME, "q-dialog--form"))
    )
    assert form_closed, "Form/dialog did not close after submission"