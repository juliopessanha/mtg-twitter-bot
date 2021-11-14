import os
import tweepy
import requests
import time
import pandas as pd
import re

folder_path = os.path.abspath("./")

#Load tweepy credentials
def get_credentials():
    #Load the credentials file
    credential_path = os.path.abspath("./").replace("mtg-scraper", "") + "credentials.txt"
    
    #Read the credentials in the following order:
    #Customer Key
    #Customer Secret
    #Access Token
    #Access Token Secret
    with open(credential_path) as f:
        credentials = f.readlines()

    f.close()
    return(credentials) #Returning list of credentials

#Download the card of the given link
def download_card(card_data, priceType):
    #Gets the card data list and the name afix definition. It may be "high" or "low"
    url = card_data[2] #Get the link from the card data list
    r = requests.get(url, allow_redirects=True) #Download
    open(folder_path + '/mtg_card_' + priceType + '.png', 'wb').write(r.content) #And save the card

#Reads the mtg card excel spreadsheet and turns it into a pandas dataframe
def get_dataframe():
    df = pd.read_excel(folder_path + '/mtg_data.xlsx')
    #simpleName is the card name but made simpler to match from the twitter text
    df['simpleName'] = df['name'].replace({',': ''}, regex=True)
    df['simpleName'] = df['simpleName'].replace({"'s": ''}, regex=True)
    df['simpleName'] = df['simpleName'].replace({":": ''}, regex=True)
    #Remove the set name like (Crimson Vow)
    df['simpleName'] = df['simpleName'].replace({r' \([^)]*\)': ''}, regex=True)
    #name is just the card name itself
    df['name'] = df['name'].replace({r' \([^)]*\)': ''}, regex=True)
    return(df)


#Get the card name and return a dataframe with the possible cards it might be
def get_specific_card(words, card_name):
    #Get the card name and make it into a list
    words = words.strip().title().split()
    
    #Test every single word in the list trying to find the matching card
    for word in words:
        if len(card_name[card_name['simpleName'].str.contains(word) == True]) > 0: 
            card_name = card_name[card_name['simpleName'].str.contains(word)]
    
    #If a card with the given name exists, those cards are selected
    #If a new name match in that subgroup, those cards are selected
    #Repeat until the end
    
    return(card_name)

#Get the lowest card price data
def lowPrice(card_data):
    #Get the highest price card from the dataframe
    card_data["lowPrice"] = pd.to_numeric(card_data['lowPrice'][card_data['lowPrice'] != '-'], downcast="float")
    lowPrice_value = card_data['lowPrice'].min()
    #Get the name of the card and the download link
    name = (card_data['name'][card_data['lowPrice'] == lowPrice_value].iloc[0])
    link = (card_data['front_image'][card_data['lowPrice'] == lowPrice_value].iloc[0])    
    
    return([name, lowPrice_value, link])

#Get the highest price card data
def highPrice(card_data):
    #Get the highest price card from the dataframe
    card_data["highPrice"] = pd.to_numeric(card_data['highPrice'][card_data['highPrice'] != '-'], downcast="float")
    highPrice_value = card_data['highPrice'].max()
    #Get the name of the card and the download link
    name = (card_data['name'][card_data['highPrice'] == highPrice_value].iloc[0])
    link = (card_data['front_image'][card_data['highPrice'] == highPrice_value].iloc[0])
    
    return([name, highPrice_value, link])

#Get tweet credentials and connect
def twitter(credentials):
    auth = tweepy.OAuthHandler(credentials[0].strip(), credentials[1].strip()) 
    auth.set_access_token(credentials[2].strip(), credentials[3].strip())
    
    api = tweepy.API(auth, wait_on_rate_limit=True) 
    return(api)


#Prepare and post tweet
def post(lowValue, highValue, api, tweet):
    
    screen_name = tweet._json['user']['screen_name']

    if lowValue[0] == highValue[0]: #If the code found only one card, it return a single image
        media_path = [folder_path + '/mtg_card_high.png']

        media_ids = [api.media_upload(i).media_id_string for i in media_path]
        
        msg = 'Hi, @%s. Here\'s your card:\n%s\n\n \
        Lowest price: $%s\n \
        Highest price: $%s' % (screen_name, highValue[0], lowValue[1], highValue[1])
    
    else: #if the code found conflicting card names, it returns the highest and lowest price among them
        media_path = [folder_path + '/mtg_card_low.png', folder_path + '/mtg_card_high.png']

        media_ids = [api.media_upload(i).media_id_string for i in media_path]
        
        msg = 'Hi, @%s. I found many cards:\n\'%s\' and \'%s\'\n\n\
        Lowest price: $%s\n\
        Highest price: $%s' % (screen_name, lowValue[0], highValue[0], lowValue[1], highValue[1])
    
    #Answer the tweet
    api.update_status(status = msg, media_ids = media_ids, in_reply_to_status_id = tweet.id)
        
#Clean the tweet to make it easier to match 
def text_preparation(text):
    text = text.lower()
    text = text.replace("'s", "")
    text = text.replace(":", "")
    text = text.replace(",", "")
    text = text.replace("(", "")
    text = text.replace(")", "")
    text = text.replace("{", "")
    text = text.replace("}", "")
    text = text.replace("[", "")
    text = text.replace("]", "")
    text = text.replace("\n", " ")
    text = re.search(r'@mtg_robot find(.*)', text)[0].replace("@mtg_robot find", "")
    
    return(text)
    
#Process a new mention and post
def process_tweet(tweet, data):
    print(tweet.full_text)
    #Get the card name
    name = text_preparation(tweet.full_text)
    print(name)
    #Find the card in the dataframe
    specific_card = get_specific_card(name, data)
    
    #Get the lowest cost card with the matching name
    lowValue = lowPrice(specific_card)
    download_card(lowValue, 'low') #Download the cheapest card
    #Get the lowest cost card with the matching name
    highValue = highPrice(specific_card)
    download_card(highValue, 'high') #Download the most expensive card
    
    post(lowValue, highValue, api, tweet) #Answer the tweet
        
if __name__ == "__main__":

    timeCounter = time.time()
    credentials = get_credentials()

    api = twitter(credentials)
    
    data = get_dataframe()
    
    #Get the last mention id
    oldMention = api.mentions_timeline()[0].id
    
    print("Waiting for mentions")
    while 1: #Loops waiting for new mentions
        try: #Tries to run
            newMentions = api.mentions_timeline(tweet_mode="extended") #Get the mentions of the last 30 seconds

            if time.time() - timeCounter > 86400: #Loads a new dataframe every 24 hours
                print("Loading new dataframe")
                data = get_dataframe()
                
            if newMentions[0].id > oldMention: #If there's new mention
                i = 0
                while 1: #Go through each new mention
                    if newMentions[i].id <= oldMention: #Stops if it tries to answer an old mention
                        oldMention = newMentions[0].id #Define new mention limit
                        break
                    else:
                        try: #tries to process and answer the tweet
                            process_tweet(newMentions[i], data) #Process the tweet and answers it
                        except: #If it breaks, skips the mention
                            print("erro")
                        i += 1
            else:
                print("-")
        except: #If the loop breaks, it will try again
           print("deu ruim")

        time.sleep(15) #Some delay
