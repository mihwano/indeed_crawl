from lxml import html
from bs4 import BeautifulSoup
from io import StringIO
import requests
import pdb
from pymongo import MongoClient
from difflib import SequenceMatcher
import time
import re
import googlemaps


#api_key = 'AIzaSyDiW5FcUKP5GZTYVE9KcFpxOeQcCLtpxZk'
api_key = 'AIzaSyCu-j55GGkiyn8fWfA_uhnu2x-SlFwjT3M'
gmaps = googlemaps.Client(key=api_key)

indeed_search = 'https://www.indeed.com/jobs?as_and=python,+data&as_phr=&as_any=GIS,+machine+learning,+backend,+software&as_not=security,+clearance,+tsl,+citizen&as_ttl=&as_cmp=&jt=all&st=&salary=&radius=25&l=Arlington,+VA&fromage=1&limit=50&sort=&psf=advsrch'
indeed_url = indeed_search


def get_posting(content):
    posting_ids = content.xpath("//div/h2[@class='jobtitle']/@id")
    posting_titles = content.xpath("//div/h2/a[@class='turnstileLink']/@title")
    posting_links = content.xpath("//div/h2/a[@class='turnstileLink']/@href")
    return posting_ids, posting_titles, posting_links


def get_baseurl(website):
    if website == 'indeed':
        return 'https://www.indeed.com'
    return


def get_company(content):
    companies = content.xpath("//div/span/span[@itemprop='name']")
    return [x.text_content().strip() for x in companies]


def get_location(content):
    locations = content.xpath("//div/span[@itemprop='jobLocation']")
    return[x.text_content().strip() for x in locations]


def get_content(url, title):
    page = requests.get(url).text
    content = html.fromstring(page)
    body = content.xpath('/html/body')
    texts = []
    for tags in body[0].findall('.//'):
        text = tags.text_content()
        if len(texts) == 0:
            texts.append(text)
        elif (len([x for x in text if x.isalpha()]) < len([x for x in text if not x.isalpha()])) or \
             (len(text) - len(text.replace('\n','')) > 0.05 * len(text)) or (len(text)<50):
            continue
        else:
            to_ignore = False
            for stuff in texts:
                similarity = SequenceMatcher(None, text, stuff).ratio()
                if  similarity > 0.4:
                    to_ignore = True
            if to_ignore == False:
                texts.append(tags.text_content())
    return texts

def scrap_ads(url, data, website):
    """ scrap basic info for each ad from the url html """
    if requests.get(url).status_code == 200:
        page = requests.get(url).text
    else:
        print("could not reach url, error: %s" %(requests.get(url).status_code))
        return

    content = html.fromstring(page)
    posting_ids, posting_titles, posting_links = get_posting(content)
    companies = get_company(content)
    locations = get_location(content)
    base_url = get_baseurl(website)
    i = 0
    for job in posting_ids:
        # text = get_content(base_url + posting_links[i], posting_titles[i])
        text = ''
        data[job] = {"posting_id": job,
                     "job_title": posting_titles[i],
                     "url_link": base_url + posting_links[i],
                     "company": companies[i],
                     "location": locations[i],
                     "job_board": website,
                     "timestamp": time.strftime("%x"),
                     "applied_to": False,
                     "interview": False,
                     "reply_sent": False,
                     "seen-interested": False,
                     "seen_uninterested": False,
                     "content": 'NA'}
        i += 1
        print("job %s of %s fetched" %(i, len(posting_ids)))
    return data


def get_address(company, location):
        place = gmaps.places(company + "," + location)
        try:
            address = place['results'][0]['formatted_address']
            lat = place['results'][0]['geometry']['location']['lat']
            lon = place['results'][0]['geometry']['location']['lng']
        except:
            try:
                place = gmaps.places(location)
                address = place['results'][0]['formatted_address']
                lat = place['results'][0]['geometry']['location']['lat']
                lon = place['results'][0]['geometry']['location']['lng']
            except:
                address = 'NA'
                lat = 'NA'
                lon = 'NA'             
        return address, lat, lon


def update_data_with_address(data):
    addresses = []; lats = []; lons = []
    for item in data:
        address, lat, lon = get_address(data[item]["company"], data[item]["location"])
        print("address retrieved for %s" %data[item]["company"])
        data[item]["address"] = address
        data[item]["lat"] = lat
        data[item]["lon"] = lon
    return data


if __name__ == "__main__":
    data = {}
    website = 'indeed'
    data = scrap_ads(indeed_url, data, website)
    data = update_data_with_address(data)

    client = MongoClient()
    db = client["jobs_db"]
    collection = db['indeed_jobs']

    for posting in data:
        collection.replace_one({'posting_id': posting}, data[posting], upsert=True)
