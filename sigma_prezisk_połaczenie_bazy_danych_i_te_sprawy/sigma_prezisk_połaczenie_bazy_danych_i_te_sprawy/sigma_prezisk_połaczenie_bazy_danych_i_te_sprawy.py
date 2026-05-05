import mysql.connector
from mysql.connector import Error
import requests
from bs4 import BeautifulSoup
import re
import time
import random  # Do generowania losowych sezonów

# Dane do po³¹czenia z baz¹ danych
hostname = "xao6f.h.filess.io"
database = "Project_everything"
port = "3307"
username = "Project_everything"
password = "27ff9f62719b4eb7cbf071aaf3f2dbce94b6676b"

# Funkcja do pobierania szczegó³ów produktu (nazwa, cena)
def scrape_product_details(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')

        # Pobranie ceny
        price_tag = soup.find('em', class_='main-price')
        if price_tag:
            price_text = price_tag.text.strip()
            price = re.sub(r'[^\d,]', '', price_text).replace(',', '.')
        else:
            price = None

        # Pobranie nazwy produktu
        name_tag = soup.find('h1', class_='name')
        if name_tag:
            name = name_tag.text.strip()
        else:
            name = "Unknown"

        return name, price
    except requests.exceptions.RequestException as e:
        print(f'[ERROR] Error fetching product details from {url}: {e}')
        return "Unknown", None

# Funkcja do pobierania linków produktów z pojedynczej strony
def scrape_page_links(url):
    unique_links = set()
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        products_div = soup.find('div', class_='products products_extended viewphot s-row')
        
        if products_div:
            links = products_div.find_all('a')
            for link in links:
                href = link.get('href')
                if href and '/pl/c/' not in href:
                    if href.startswith('/'):
                        full_url = 'https://pnos.pl' + href
                    else:
                        full_url = href
                    unique_links.add(full_url)
    except requests.exceptions.RequestException as e:
        print(f'[ERROR] Error fetching page {url}: {e}')
    return unique_links

try:
    # Po³¹czenie z baz¹ danych
    connection = mysql.connector.connect(host=hostname, database=database, user=username, password=password, port=port)
    
    if connection.is_connected():
        print("Connected to MySQL Server")
        cursor = connection.cursor()
        
        # Usuniêcie danych i reset AUTO_INCREMENT
        cursor.execute("DELETE FROM warzywa")  # Usuwa wszystkie wiersze z tabeli
        cursor.execute("ALTER TABLE warzywa AUTO_INCREMENT = 1")  # Resetuje licznik AUTO_INCREMENT
        connection.commit()
        
        # Scrape links
        base_url = 'https://pnos.pl/Tradycyjne-nasiona-warzyw'
        total_pages = 3
        all_links = set()

        for page in range(1, total_pages + 1):
            page_url = f'{base_url}/{page}'
            print(f'Scraping page: {page_url}')
            all_links.update(scrape_page_links(page_url))
            time.sleep(1)  # OpóŸnienie dla bezpieczeñstwa
        
        # Sezony do losowania
        seasons = ["lato", "jesien", "wiosna"]
        product_seasons = {}  # S³ownik do przechowywania przypisanych sezonów
        
        # Scrape product details and insert into database
        for link in all_links:
            print(f'Scraping product: {link}')
            name, price = scrape_product_details(link)
            
            if price is None:
                price = 0.0  # Ustaw domyœln¹ wartoœæ dla brakuj¹cych cen
            
            # Wyodrêbnienie wagi z nazwy
            match = re.search(r'(\d+g)', name.lower())
            waga = match.group(1) if match else "Brak informacji"

            # Normalizacja nazwy (usuniêcie wagi dla porównania)
            base_name = re.sub(r'\d+g', '', name.lower()).strip()
            
            # SprawdŸ, czy nazwa ju¿ ma przypisany sezon
            if base_name in product_seasons:
                season = product_seasons[base_name]
            else:
                season = random.choice(seasons)
                product_seasons[base_name] = season
            
            # Wstaw dane do tabeli
            cursor.execute("""
                INSERT INTO warzywa (product_name, price, product_link, waga, sezon)
                VALUES (%s, %s, %s, %s, %s)
            """, (name, price, link, waga, season))
        
        connection.commit()  # Zatwierdz zmiany
        print("Data successfully inserted and updated in 'warzywa' table.")
except Error as e:
    print(f"Error while connecting to MySQL: {e}")
finally:
    if connection.is_connected():
        cursor.close()
        connection.close()
        print("MySQL connection is closed")
