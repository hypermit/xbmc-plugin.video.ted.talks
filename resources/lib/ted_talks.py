import sys
import urllib
import ted_talks_scraper
import plugin
import settings
from talkDownloader import Download
from model.fetcher import Fetcher
from model.user import User
from model.rss_scraper import NewTalksRss
from model.favorites_scraper import Favorites
from model.speakers_scraper import Speakers
from model.themes_scraper import Themes
from model.util import resizeImage
from model.search_scraper import Search
import menu_util
import os
import time
import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
import itertools


def login(user_scraper, username, password):
    user_details = user_scraper.login(username, password)
    if not user_scraper:
        xbmcgui.Dialog().ok(plugin.getLS(30050), plugin.getLS(30051))
    return user_details


class UI:

    def __init__(self, get_HTML, ted_talks, user):
        self.get_HTML = get_HTML
        self.ted_talks = ted_talks
        self.user = user
        xbmcplugin.setContent(int(sys.argv[1]), 'movies')

    def endofdirectory(self, sortMethod='title', updateListing=False):
        # set sortmethod to something xbmc can use
        if sortMethod == 'title':
            sortMethod = xbmcplugin.SORT_METHOD_LABEL
        elif sortMethod == 'date':
            sortMethod = xbmcplugin.SORT_METHOD_DATE
        elif sortMethod == 'none':
            sortMethod = xbmcplugin.SORT_METHOD_NONE

        # Sort methods are required in library mode.
        xbmcplugin.addSortMethod(int(sys.argv[1]), sortMethod)
        # let xbmc know the script is done adding items to the list.
        xbmcplugin.endOfDirectory(handle=int(sys.argv[1]), updateListing=updateListing)

    def addItem(self, title, mode, url=None, img='', args={}, video_info={}, isFolder=True, total_items=0):
        # Create action url
        args['mode'] = mode;
        if url:
            args['url'] = url
        if img:
            img = resizeImage(img)
            args['icon'] = img
        args = [k + '=' + urllib.quote_plus(v.encode('ascii', 'ignore')) for k, v in args.iteritems()]
        action_url = sys.argv[0] + '?' + "&".join(args)

        li = xbmcgui.ListItem(label=title, iconImage=img, thumbnailImage=img)
        video_info = dict((k, v) for k, v in video_info.iteritems() if k in ['date', 'plot'])
        if video_info:
            li.setInfo('video', video_info)
        if 'duration' in video_info:
            # To set with second granularity must do this rather than via setInfo
            li.addStreamInfo('video', { 'duration' : video_info['duration'] })
        if not isFolder:
            li.setProperty("IsPlayable", "true")  # let xbmc know this can be played, unlike a folder.
            context_menu = menu_util.create_context_menu(getLS=plugin.getLS)
            li.addContextMenuItems(context_menu, replaceItems=True)
        else:
            li.addContextMenuItems([], replaceItems=True)
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=action_url, listitem=li, isFolder=isFolder, totalItems=total_items)

    def playVideo(self, url, icon):
        subs_language = settings.get_subtitle_languages()
        title, url, subs, info_labels = self.ted_talks.getVideoDetails(url=url, video_quality=settings.video_quality, subs_language=subs_language)
        li = xbmcgui.ListItem(title, iconImage=icon, thumbnailImage=icon, path=url)
        li.setInfo(type='Video', infoLabels=info_labels)
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, li)
        if subs:
            # If not we either don't want them, or should have displayed a notification.
            subs_file = os.path.join(xbmc.translatePath("special://temp"), 'ted_talks_subs.srt')
            fh = open(subs_file, 'w')
            try:
                fh.write(subs.encode('utf-8'))
            finally:
                fh.close()
                player = xbmc.Player()
            # Up to 30s to start
            start_time = time.time()
            while not player.isPlaying() and time.time() - start_time < 30:
                time.sleep(1)
            if player.isPlaying():
                xbmc.Player().setSubtitles(subs_file);
            else:
                # No user message: user was probably already notified of a problem with the stream.
                plugin.report('Could not show subtitles: timed out waiting for player to start.')

    def navItems(self, navItems, mode):
        if navItems['next']:
            self.addItem(plugin.getLS(30020), mode, navItems['next'])
        if navItems['previous']:
            self.addItem(plugin.getLS(30021), mode, navItems['previous'])

    def showCategories(self):
        self.addItem(plugin.getLS(30001), 'newTalksRss', video_info={'Plot':plugin.getLS(30031)})
        self.addItem(plugin.getLS(30002), 'speakers', video_info={'Plot':plugin.getLS(30032)})
        self.addItem(plugin.getLS(30003), 'themes', video_info={'Plot':plugin.getLS(30033)})
        self.addItem(plugin.getLS(30004) + "...", 'search', video_info={'Plot':plugin.getLS(30034)})
        if settings.username:
            self.addItem(plugin.getLS(30005), 'favorites', video_info={'Plot':plugin.getLS(30035)})
        self.endofdirectory()

    def newTalksRss(self):
        newTalks = NewTalksRss(plugin.report)
        for talk in newTalks.get_new_talks():
            self.addItem(title=talk['title'], mode='playVideo', url=talk['link'], img=talk['thumb'], video_info=talk, isFolder=False)
        self.endofdirectory(sortMethod='date')

    def speakerGroups(self):
        for i in range(65, 91):
            letter = chr(i)
            self.addItem(plugin.getLS(30006) + letter, 'speakerGroup', letter, isFolder=True)
        self.endofdirectory()

    def speakers(self, letter):
        speakers_generator = Speakers(self.get_HTML).get_speakers_for_letter(letter)
        speaker_count = itertools.islice(speakers_generator, 1).next()
        for title, link, img in speakers_generator:
            self.addItem(title, 'speakerVids', link, img, isFolder=True, total_items=speaker_count)
        self.endofdirectory()

    def speakerVids(self, url):
        talks_generator = Speakers(self.get_HTML).get_talks_for_speaker(url)
        for title, link, img in talks_generator:
            self.addItem(title, 'playVideo', link, img, isFolder=False)
        self.endofdirectory()

    def themes(self):
        themes = Themes(self.get_HTML)
        for title, link, img, count in themes.get_themes():
            # Need to associate count with the item so that we can use it when that one selected.
            self.addItem(title, 'themeVids', link, img, isFolder=True)
        self.endofdirectory()

    def themeVids(self, url):
        themes = Themes(self.get_HTML)
        for title, link, img in themes.get_talks(url):
            self.addItem(title, 'playVideo', link, img, isFolder=False)
        self.endofdirectory()

    def favorites(self):
        # attempt to login
        userID, realname = login(self.user, settings.username, settings.password)
        if userID:
            for title, url, img in Favorites(plugin.report, self.get_HTML).getFavoriteTalks(userID):
                self.addItem(title, 'playVideo', url=url, img=img, isFolder=False)
            self.endofdirectory()


class Action(object):
    '''
    Some action that can be executed by the user.
    '''

    def __init__(self, mode, required_args, logger=None, *args, **kwargs):
        self.mode = mode
        self.required_args = set(required_args)
        self.logger = logger

    def run(self, args):
        good = self.required_args.issubset(args.keys())
        if good:
            self.run_internal(args)
        else:
            self.report_problem(args)

    def report_problem(self, args):
        # The theory is that this might happen for a favorite from another version;
        # though we can't be sure about the cause hence vagueness in friendly message.
        friendly_message = "Action '%s' failed. Try re-creating the item." % (self.mode)
        self.logger("%s\nBad arguments: %s" % (friendly_message, args), friendly_message)


class PlayVideoAction(Action):

    def __init__(self, ui, *args, **kwargs):
        super(PlayVideoAction, self).__init__('playVideo', ['url', 'icon'], *args, **kwargs)
        self.ui = ui

    def run_internal(self, args):
        self.ui.playVideo(args['url'], args['icon'])


class NewTalksAction(Action):

    def __init__(self, ui, *args, **kwargs):
        super(NewTalksAction, self).__init__('newTalksRss', [], *args, **kwargs)
        self.ui = ui

    def run_internal(self, args):
        self.ui.newTalksRss()


class SpeakersAction(Action):

    def __init__(self, ui, *args, **kwargs):
        super(SpeakersAction, self).__init__('speakers', [], *args, **kwargs)
        self.ui = ui

    def run_internal(self, args):
        self.ui.speakerGroups()


class SpeakerGroupAction(Action):

    def __init__(self, ui, *args, **kwargs):
        super(SpeakerGroupAction, self).__init__('speakerGroup', ['url'], *args, **kwargs)
        self.ui = ui

    def run_internal(self, args):
        self.ui.speakers(args['url'])


class SpeakerVideosAction(Action):

    def __init__(self, ui, *args, **kwargs):
        super(SpeakerVideosAction, self).__init__('speakerVids', ['url'], *args, **kwargs)
        self.ui = ui

    def run_internal(self, args):
        self.ui.speakerVids(args['url'])


class ThemesAction(Action):

    def __init__(self, ui, *args, **kwargs):
        super(ThemesAction, self).__init__('themes', [], *args, **kwargs)
        self.ui = ui

    def run_internal(self, args):
        self.ui.themes()


class ThemeVideosAction(Action):

    def __init__(self, ui, *args, **kwargs):
        super(ThemeVideosAction, self).__init__('themeVids', ['url'], *args, **kwargs)
        self.ui = ui

    def run_internal(self, args):
        self.ui.themeVids(args['url'])


class FavoritesAction(Action):

    def __init__(self, ui, *args, **kwargs):
        super(FavoritesAction, self).__init__('favorites', [], *args, **kwargs)
        self.ui = ui

    def run_internal(self, args):
        self.ui.favorites()


class SearchActionBase(Action):

    def __init__(self, ui, get_HTML, *args, **kwargs):
        super(SearchActionBase, self).__init__(*args, **kwargs)
        self.ui = ui
        self.get_HTML = get_HTML

    def __add_items__(self, search_term, page, current_items, update_listing):
        talks_generator = Search(self.get_HTML).get_talks_for_search(search_term, page)
        remaining_talks = itertools.islice(talks_generator, 1).next()
        search_results = list(itertools.chain(current_items, talks_generator))
        for title, link, img in search_results:
            self.ui.addItem(title, 'playVideo', link, img, isFolder=False)
        if remaining_talks:
            self.ui.addItem(plugin.getLS(30022), 'searchMore', args={'search_term': search_term, 'page': str(page + 1)})
        self.ui.endofdirectory(sortMethod='none', updateListing=update_listing)

        return search_results


class SearchAction(SearchActionBase):

    def __init__(self, *args, **kwargs):
        # Well this is a mess. More research needed...
        super(SearchAction, self).__init__(*(args + ('search', [])), **kwargs)

    def run_internal(self, args):
        keyboard = xbmc.Keyboard(settings.get_current_search(), plugin.getLS(30004))
        keyboard.doModal()

        if not keyboard.isConfirmed():
            return

        search_term = keyboard.getText()
        settings.set_current_search(search_term)
        self.__add_items__(search_term, 1, [], False)


class SearchMoreAction(SearchActionBase):

    def __init__(self, *args, **kwargs):
        # Well this is a mess. More research needed...
        super(SearchMoreAction, self).__init__(*(args + ('searchMore', ['search_term', 'page'])), **kwargs)

    def run_internal(self, args):
        search_term = args['search_term']
        page = int(args['page'])
        self.__add_items__(search_term, page + 1, [], False)


class DownloadVideoAction(Action):

    def __init__(self, logger, main):
        super(DownloadVideoAction, self).__init__('downloadVideo', ['url'], logger)
        self.main = main

    def run_internal(self, args):
        self.main.downloadVid(args['url'], False)


class Main:

    def __init__(self, args_map):
        self.args_map = args_map
        self.get_HTML = Fetcher(plugin.report, xbmc.translatePath).getHTML
        self.user = User(self.get_HTML)
        self.ted_talks = ted_talks_scraper.TedTalks(self.get_HTML, plugin.report)

    def downloadVid(self, url):
        video = self.ted_talks.getVideoDetails(url)
        if settings.download_mode == 'true':
            downloadPath = xbmcgui.Dialog().browse(3, plugin.getLS(30096), 'files')
        else:
            downloadPath = settings.download_path
        if downloadPath:
            Download(plugin.getLS, video['Title'], video['url'], downloadPath)

    def run(self):
        ui = UI(self.get_HTML, self.ted_talks, self.user)
        if 'mode' not in self.args_map:
            ui.showCategories()
        else:
            modes = [
                PlayVideoAction(ui, logger=plugin.report),
                NewTalksAction(ui, logger=plugin.report),
                SearchAction(ui, self.get_HTML, logger=plugin.report),
                SearchMoreAction(ui, self.get_HTML, logger=plugin.report),
                SpeakersAction(ui, logger=plugin.report),
                SpeakerGroupAction(ui, logger=plugin.report),
                SpeakerVideosAction(ui, logger=plugin.report),
                ThemesAction(ui, logger=plugin.report),
                ThemeVideosAction(ui, logger=plugin.report),
                FavoritesAction(ui, logger=plugin.report),
                # DownloadVideoAction(plugin.report, self),
            ]
            modes = dict([(m.mode, m) for m in modes])
            mode = self.args_map['mode']
            if mode in modes:
                modes[mode].run(self.args_map)
            else:
                # Bit of a hack (cough)
                Action(mode, [], plugin.report).report_problem(self.args_map)
