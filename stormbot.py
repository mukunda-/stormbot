#-----------------------------------------------------------------------------------------
# Stormbot
# A basic ChatGPT app that generates storm reports and cultural trivia.
# (C) 2023 Mukunda Johnson <mukunda@mukunda.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#-----------------------------------------------------------------------------------------
import os, openai, re, feedparser, requests, sys, random
from datetime import datetime, timedelta
from dateutil.parser import parse as dateparse
openai.organization = os.getenv("OPENAI_ORG")
openai.api_key = os.getenv("OPENAI_API_KEY")
slack_webhook = os.getenv("STORMBOT_SLACK_WEBHOOK")

VERSION = "1.0.0"

#-----------------------------------------------------------------------------------------
# Fetch the latest article description from an RSS feed.
def read_latest_rss(url):
   try:
      rss = feedparser.parse(url)
      if len(rss.entries) == 0: return ""
      
      latest = rss.entries[0].summary
      latest = re.sub(r'<[^>]*>', ' ', latest)
      return latest.rstrip()
   except Exception as e:
      print("Failure reading rss feed", e, file=sys.stderr)
      return ""

#-----------------------------------------------------------------------------------------
# Search an RSS feed for any articles about hurricanes/cyclones and return the summary.
def scan_for_storms(url):
   try:
      rss = feedparser.parse(url)
      for entry in rss.entries:
         # Skip old articles
         if not entry.get("published") or (dateparse(entry.published).replace(tzinfo=None) < datetime.now() - timedelta(days=7)): continue
         t = entry.title.lower()
         if "hurricane" in t or "tropical storm" in t or "tropical cyclone" in t:
            return entry.get("title", "") + "\n" + entry.get("summary", "")
      return ""
   except Exception as e:
      print("Failure scanning rss feed", e, file=sys.stderr)
      return ""
   
#-----------------------------------------------------------------------------------------
# Fetch a plain text file from a URL.
def get_plain_text(url):
   try:
      return requests.get(url).text
   except Exception as e:
      print("Failure getting plain text", e, file=sys.stderr)
      return ""

#-----------------------------------------------------------------------------------------
# Fetch the storm report from ChatGPT.
def get_storm_report():

   # https://www.nhc.noaa.gov/aboutrss.shtml
   basic_feed_urls = [
      "https://www.nhc.noaa.gov/xml/TWOAT.xml",
      "https://www.nhc.noaa.gov/xml/TWOEP.xml",
      "https://www.nhc.noaa.gov/xml/TWOCP.xml",
   ]

   feeds = []
      
   feed_content = ""
   for feed in basic_feed_urls:
      feeds += [read_latest_rss(feed)]

   # Google World News
   feeds += [scan_for_storms("https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en")]

   # http://tropic.ssec.wisc.edu/
   feeds += [
      get_plain_text("https://tropic.ssec.wisc.edu/real-time/misc/wxdisc21.txt"), # Australia/Fiji region
      get_plain_text("https://tropic.ssec.wisc.edu/real-time/misc/wxdisc41.txt"), # Indian Ocean
      get_plain_text("https://tropic.ssec.wisc.edu/real-time/misc/wxdisc21.txt"), # West Pacific
   ]

   feed_content = "\n\n---\n\n".join(feeds)

   content = f"""
Check the following tropical weather reports and discussions for any tropical cyclones or hurricanes this week.

{feed_content}
   """.strip()

   print("STORM PROMPT\n", len(content), content)
   # todo: backoff retry
   completion = openai.ChatCompletion.create(
      model="gpt-3.5-turbo",
      messages=[
         {
            "role": "user",
            "content": content,
            "name": "Weatherman"
         }
      ],
      max_tokens=1000,
      # I think a lower temperature here helps to not ignore hurricanes :)
      # Otherwise it has more freedom to make stuff up.
      temperature=0.25)
   return completion.choices[0].message.content

#-----------------------------------------------------------------------------------------
# Generate some cultural trivia. The main variable is the month and day.
def get_cultural_trivia():
   
   # Get the current month and day with no leading zeroes
   now = datetime.now()
   date = now.strftime("%B %d").replace(" 0", " ")

   # I find that being direct (and not polite) helps to evade fluff from the response.
   content = f"""
List 5 diversive cultural trivia that is related to the week starting on {date}. Do not mention events that are tied to a specific year. Do not mention any dates.
   """.strip()

   completion = openai.ChatCompletion.create(
      model="gpt-3.5-turbo",
      messages=[{
         "role": "user",
         "content": content,
         "name": "DiversityBot"
      }],
      max_tokens=2000)
   return completion.choices[0].message.content

#-----------------------------------------------------------------------------------------
def get_activity_inspiration():
   # try:
   #    content = requests.get("https://www.random-generator.org.uk/activity/").text

   #    content = re.search(r'https://www\.random-generator\.org\.uk/covid-19/">Lockdown Activity Generator</a><br/><br/>(.*)<h2>Generate Some More</h2>', content)[1]

   #    content = re.split(r'<br/>', content)
   #    content = [i for i in content if i != '']
   #    print("got inspo", content)
   #    return "\n".join(content)
   # except Exception as e:
   #    print(e, file=sys.stderr)
   #    return ""
   content = requests.get("https://random-word-api.herokuapp.com/word?number=3").json()
   content = ", ".join(content)
   return content

#-----------------------------------------------------------------------------------------
def get_fun_activities():
   print("Generating activity...")
   # Get the current month and day with no leading zeroes
   now = datetime.now()
   month = now.strftime("%B")

   # Prompt to generate this: "Generate a list of 100 topics about hobbies."
   topic = random.choice([
      "photography","painting","gardening","cooking","writing","reading","fishing","knitting","sewing","pottery","woodworking","sculpting","playing a musical instrument","dancing","birdwatching","hiking","camping","cycling","running","yoga","meditation","sketching","calligraphy","graphic design","baking","cross-stitching","origami","embroidery","beekeeping","candle making","model building","coin collecting","stamp collecting","wine tasting","brewing beer","playing board games","chess","video gaming","archery","rock climbing","martial arts","magic tricks","singing","acting","stand-up comedy","cosplay","diy projects","scrapbooking","jewelry making","pottery","interior design","crossword puzzles","sudoku","home brewing","wine making","bird photography","beekeeping","creative writing","hiking and nature photography","soap making","kite flying","astronomy","collecting vintage items","geocaching","djing","making short films","wine pairing","brewing coffee","urban gardening","chess puzzles","stand-up paddleboarding","surfing","diy home improvement projects","rollerblading","jigsaw puzzles","coin flipping tricks","virtual reality gaming","quilting","photography editing and retouching","wood carving","digital art","comic book collecting","writing poetry","archery","playing card tricks","making homemade candles","terrarium gardening","toy collecting","marathon running","mountain biking","needle felting","card making","paper mache crafts","tea tasting","airbrush painting","photography composition techniques","dj mixing","stargazing","macrame","bonsai tree cultivation"
   ])

   # "Generate for me" rather than asking a question resulted in more direct descriptions.
   content = f"""
Generate for me a fun weekend activity that is related to {topic} and the month of {month}.
   """.strip()

   print('Prompt:', content)

   completion = openai.ChatCompletion.create(
      model="gpt-3.5-turbo",
      messages=[
         {
            "role": "user",
            "content": content,
            "name": "InclusionBot"
         }
      ],
      temperature=0.85,
      max_tokens=2000)
   return completion.choices[0].message.content

#-----------------------------------------------------------------------------------------
digest = ""

#-----------------------------------------------------------------------------------------
# Append text to digest and print it to the console.
def log(text):
   global digest
   digest = digest + text + "\n"
   print(text)

#-----------------------------------------------------------------------------------------
# Append text to digest and print it to the console.
# For each line, prepend "> " to make it a quote.
def log2(text):
   global digest
   digest = digest + "> " + text.replace("\n", "\n> ") + "\n"
   print(text)
   
#-----------------------------------------------------------------------------------------
def main():
   global digest
   print("Stormbot", VERSION)

   log("*Beep boop! Here is your weekly tropical outlook report:*")
   log2(get_storm_report())

   log("")
   log("")
   log("*I do more than just report inclement weather. Learning about cultural trivia is a great way to expand diversity and inclusion in the workplace. Here are a few notes about this week:*")
   log2(get_cultural_trivia())

   log("")
   log("")
   log("*If you are not busy evacuating for a hurricane, here is a fun and engaging weekend activity that I have generated for you:*")
   log2(get_fun_activities())

   log("")
   log("")
   log("*I hope that you have a restful and relaxing break! See you next week—I am sure that it will be a productive one! Beep boop! ☺*")

   print(requests.post(slack_webhook, json={
      "blocks": [{
         "type": "section",
         "text": {
            "type": "mrkdwn",
            "text": digest
         }
      }]
   }))

#-----------------------------------------------------------------------------------------
if __name__ == "__main__": main()
