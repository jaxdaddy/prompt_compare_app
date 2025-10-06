import requests
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'
}

search_url = f"https://duckduckgo.com/html/?q=financial%20news%20for%20AAPL"
response = requests.get(search_url, headers=headers)
soup = BeautifulSoup(response.text, "html.parser")

print(soup.prettify())
