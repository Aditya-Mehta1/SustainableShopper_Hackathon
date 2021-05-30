#import depndencies
from flask import Flask, redirect, url_for, render_template, Response, request
import cv2
from pyzbar import pyzbar
import bs4 as bs
import sqlite3
import os
import ssl
import requests
import re

# barcode is a global variable which is used to store the value of a barcode when detected
barcode = 0


# search is a function which searches for a product on amazon and stores a link to product page
def search(barcode_number):
    if (not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None)):
        ssl._create_default_https_context = ssl._create_unverified_context
    url = "https://www.amazon.in/s?k=" + str(barcode_number)
    headers = {
        'authority': 'www.amazon.com',
        'pragma': 'no-cache',
        'cache-control': 'no-cache',
        'dnt': '1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (X11; CrOS x86_64 8172.45.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.64 Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'sec-fetch-site': 'none',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-dest': 'document',
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
    }
    response = requests.get(url, headers=headers)
    source = response.text
    soup = bs.BeautifulSoup(source, 'html.parser')
    link = ''
    for links in soup.find_all('a'):
        link = links.get('href')
        if link:
            if "keywords=" + str(barcode_number) in link:
                link = "amazon.in" + link
                break
    conn = sqlite3.connect('products.sqlite')
    cur = conn.cursor()
    cur.execute('INSERT INTO Products_To_Search(Barcode, Field2) VALUES(?,?)',
                (barcode_number, link))
    cur.close()
    conn.commit()


# search other stuff parses through the product page(in HTML format) and uses it to return a dictionary of product information
def search_other_stuff(path, barcode_number):
    file = open(path, "r")
    source = file.read()

    # Dictionary
    AllInformation = dict()
    AllInformation['Barcode Number'] = barcode_number
    AllInformation["Package Information"] = list()
    AllInformation["Materials"] = list()
    AllInformation["Ingredients"] = list()

    # List of materials to find
    Materials = ["cotton",
                 "leather",
                 "denim",
                 "nylon",
                 "polyester",
                 "jute"
                 "linen",
                 "khadi",
                 "wool",
                 "acrylic",
                 "alpaca",
                 "carbon Fiber",
                 "hemp"
                 "elastane",
                 "spandex",
                 "flax fiber",
                 "glass fiber",
                 "silk"]

    # To find package information
    soup = bs.BeautifulSoup(source, 'html.parser')
    for trs in soup.find_all("tr", attrs={}):
        ths = trs.find(
            "th", attrs={"class": "a-color-secondary a-size-base prodDetSectionEntry"})
        if ths:
            if ths.text.strip() == "Package Information":
                print(trs.find("td").text.strip())
                AllInformation["Package Information"].append(
                    trs.find("td").text.strip().lower())

    index = 0
    # To find materials
    desc = soup.find('div', attrs={"id": "feature-bullets"})
    if desc:
        info = desc.find_all('span')
        for tags in info:
            for material in Materials:
                if material in tags.text.lower():
                    information = tags.text.lower()
                    index = information.lower().index(material)
                    temp = information[:index]
                    percent = re.findall("[0-9]+%+", temp)[0]
                    information = information[index:]
                    AllInformation['Materials'].append((material, percent))

    # To find ingredients
    ImportantInformation = soup.find(
        'div', attrs={"id": "important-information"})
    if ImportantInformation:
        Div = ImportantInformation.find('div')
        if Div:
            ps = Div.find_all('p')
            for p in ps:
                if p.text:
                    ingredients = p.text
                    ingredients = ingredients.replace(' ', '')
                    ingredient = ingredients.replace(',', ' ').split()
                    AllInformation['Ingredients'] = ingredient
    print(AllInformation)
    return AllInformation


# search sustainablity uses the product information to score it
def search_sustainability(AllInformation):
    conn = sqlite3.connect('products.sqlite')
    cur = conn.cursor()

    SustainablityScores = dict()
    SustainablityScores['Materials'] = list()
    SustainablityScores['Package Information'] = list()
    SustainablityScores['Ingredients'] = list()

    for (material, percent) in AllInformation["Materials"]:
        cur.execute(
            'SELECT Field2 FROM Materials WHERE Textile = ?', (material,))
        score = cur.fetchone()
        if score:
            SustainablityScores['Materials'].append(
                (material, score[0], percent))

    for material in AllInformation["Package Information"]:
        cur.execute(
            'SELECT Field2 FROM PackagingMaterial WHERE Material = ?', (material,))
        score = cur.fetchone()
        if score:
            SustainablityScores['Package Information'].append(
                (material, score[0]))

    for material in AllInformation["Ingredients"]:
        cur.execute('SELECT Name FROM Ingredients')
        all_materials = cur.fetchall()
        if (material,) in all_materials:
            SustainablityScores['Ingredients'].append(material.lower())

    cur.close()
    print(SustainablityScores)

    """
    Scoring the product
    """

    i = 0
    sum_m = 0
    sum_p = 0
    sum_i = 0

    n = len(SustainablityScores['Materials'])
    if n != 0:
        i = i + 1
        for (material, score, percent) in SustainablityScores['Materials']:
            percent = int(percent.strip().replace("%", ""))
            sum_m = sum_m + score * percent / 100
        if sum_m < 100:
            sum_m = 1
        elif sum_m < 200:
            sum_m = 2
        else:
            sum_m = 3

    n = len(SustainablityScores['Package Information'])
    if n != 0:
        i = i + 1
        for (material, score) in SustainablityScores['Package Information']:
            sum_p += score
        sum_p = sum_p / n

    n = len(SustainablityScores['Ingredients'])
    if n != 0:
        i = i + 1
        sum_i = len(SustainablityScores['Ingredients'])
    if (i != 0):
        score = (sum_p + sum_m + sum_i) / i
    else:
        score = 0
    conn = sqlite3.connect('products.sqlite')
    cur = conn.cursor()
    cur.execute('INSERT INTO ProductsDB(Barcode, Score, Material, Packaging_Info, Ingredients) VALUES (?,?,?,?,?)', (
        AllInformation['Barcode Number'], score, ' '.join(
            [str(elem) for elem in AllInformation['Materials']]),
        ' '.join([str(elem)
                 for elem in AllInformation['Package Information']]),
        ' '.join([str(elem) for elem in AllInformation['Ingredients']])))
    cur.close()
    conn.commit()


# function to read barcodes in an opencv frame
def read_barcodes(frame):
    barcodes = pyzbar.decode(frame)
    # trying to find the barcode in the picture
    barcode_number = 0

    for barcode in barcodes:
        # Making a rectangle around the barcode if found
        x, y, w, h = barcode.rect
        # Decoding the value of the barcode
        barcode_number = barcode.data.decode('utf-8')
        # Showing the rectangle around detected barcode using open_cv
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

    return (frame, barcode_number)


# generator which generates video output to /videofeed
def get_video():
    video_feed = cv2.VideoCapture(0)
    ret, frame = video_feed.read()
    while ret:
        ret, frame = video_feed.read()
        frames = read_barcodes(frame)
        frame = frames[0]
        barcode_number = frames[1]
        if barcode_number != 0:
            global barcode
            barcode = barcode_number
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


# creating a flask app
app = Flask(__name__)

# app route for the home page


@app.route("/", methods=["POST", "GET"])
def home_page():
    if request.method == 'POST':
        return redirect(url_for("results_page", barcode=barcode))
    else:
        return render_template('index.html')
        # elif barcode != 0:

# app route for video feed


@app.route('/video_feed')
def video_feed():
    return Response(get_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

# app route for the results page


@app.route("/results-<barcode>")
def results_page(barcode):
    conn = sqlite3.connect('products.sqlite')
    cur = conn.cursor()
    cur.execute('SELECT * FROM ProductsDB WHERE Barcode = ?', (barcode,))
    AllInformation = cur.fetchone()
    if AllInformation is None:
        search(barcode)
        return render_template('results.html', success_or_fail1="fail", barcode=barcode)
    scores = {
        0: "No information on this product is available.",
        1: "Low score. This is product is very sustainable!",
        2: "Medium score. There may be more sustainable alternatives...",
        3: "High score. Very Unsustainable. Please look for alternatives!"}
    score_n = int(AllInformation[1])
    score = str(scores[score_n])
    Materials = (''.join([str(elem) for elem in AllInformation[2]])).replace(')', "").replace('(', '').replace('\'',
                                                                                                               '')
    Packaging_Information = (
        ''.join([str(elem) for elem in AllInformation[3]])).replace(')', "")
    Ingredients = (''.join([str(elem)
                   for elem in AllInformation[4]])).replace(')', "")
    if len(Materials) == 0:
        Materials = "None"
    if len(Packaging_Information) == 0:
        Packaging_Information = "None"
    if len(Ingredients) == 0:
        Ingredients = "None"
    print(score_n)
    if score_n == 0:
        name = 'fail'
    elif score_n == 1:
        name = url_for('static', filename='images/Low.png')
    elif score_n == 2:
        name = url_for('static', filename='images/Medium.png')
    else:
        name = url_for('static', filename='images/High.png')
    return render_template('results.html', barcode=barcode, success_or_fail2="fail", score=score, Materials=Materials,
                           Packaging_Type=Packaging_Information, Ingredients=Ingredients, name=name)

# app route for the user input page


@app.route("/User_input-<barcode>", methods=["POST", "GET"])
def User_input(barcode):
    if request.method == "POST":
        Material = request.form['Material']
        Packaging_Type = request.form['Packaging Type']
        Ingredients = request.form['Ingredients']
        AllInformation = dict()
        AllInformation['Barcode Number'] = barcode
        AllInformation["Package Information"] = list()
        AllInformation["Materials"] = list()
        AllInformation["Ingredients"] = list()

        Ingredients = Ingredients.replace(' ', '')
        AllInformation['Ingredients'] = Ingredients.replace(',', ' ').split()

        # List of materials to find
        Materials = ["cotton",
                     "leather",
                     "denim",
                     "nylon",
                     "polyester",
                     "jute"
                     "linen",
                     "khadi",
                     "wool",
                     "acrylic",
                     "alpaca",
                     "carbon Fiber",
                     "hemp"
                     "elastane",
                     "spandex",
                     "flax fiber",
                     "glass fiber",
                     "silk"]

        for material in Materials:
            if material in Material.lower():
                information = Material.lower()
                index = information.lower().index(material)
                temp = information[:index]
                percent = "100%"
                try:
                    percent = re.findall("[0-9]+%+", temp)[0]
                except IndexError:
                    pass
                information = information[index:]
                AllInformation['Materials'].append((material, percent))

        AllInformation["Package Information"].append(Packaging_Type.lower())
        search_sustainability(AllInformation)
        return redirect(url_for("results_page", barcode=barcode))
    else:
        return render_template('User_input.html', barcode=barcode)


# main run
if __name__ == '__main__':
    app.run(debug=True)
