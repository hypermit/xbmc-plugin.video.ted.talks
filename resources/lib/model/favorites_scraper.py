from url_constants import URLTED, URLFAVORITES, URLADDREMFAV
from BeautifulSoup import SoupStrainer, MinimalSoup as BeautifulSoup
from util import resizeImage
import simplejson
import re

class Favorites:

    def __init__(self, logger, get_HTML):
        self.logger = logger
        self.get_HTML = get_HTML

    def getFavoriteTalks(self, userID, url=URLFAVORITES):
        if userID:
            html = self.get_HTML(url + userID)
            talkContainer = SoupStrainer(attrs={'class':re.compile('col clearfix')})
            for talk in BeautifulSoup(html, parseOnlyThese=talkContainer):
                title = talk.a['title']
                link = URLTED + talk.a['href']
                pic = resizeImage(talk.a.img['src'])
                yield {'url':link, 'Title':title, 'Thumb':pic}
        else:
            self.logger('invalid user object')

    def addToFavorites(self, talkID):
        return self.toggle_favorite('add', talkID)

    def removeFromFavorites(self, talkID):
        return self.toggle_favorite('remove', talkID)

    def toggle_favorite(self, verb, talkID):
        url = URLADDREMFAV % (verb)
        response = self.get_HTML(url, 'id=%s&type=talks' % (talkID))
        if not response:
            msg = 'failed to %s favorite with id: %s' % (verb, talkID)
            self.logger(msg)
            return False
        response = simplejson.loads(response)
        return response['status'] == 'success'

