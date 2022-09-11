from src.service import create_yt_service
from pytube import Channel

API_KEY = ""

service = create_yt_service(API_KEY)


def getVideoDetail(video_ids: list) -> str:
    part_string = 'contentDetails,statistics,snippet,topicDetails,recordingDetails,localizations'

    response = service.videos().list(
        part=part_string,
        id=video_ids
    ).execute()

    return response


def getChannelDetail(channel_ids: list) -> str:
    """Call YT Channel API

    Args:
        channel_ids (list): list of channel details

    Returns:
        str: html return from api, containing channels details, stated in part_string
    """
    part_string = 'snippet,brandingSettings,statistics,topicDetails'

    response = service.channels().list(
        part=part_string,
        id=channel_ids,
        maxResults=50
    ).execute()

    return response

def getCommentDetail(videoId: str) -> str:
    """Call YT Channel API

    Args:
        video_ids (list): a videoId that comments will be extracted from.

    Returns:
        str: html return from api, containing comments details, stated in part_string
    """
    responses = []
    part_string = 'id, snippet'
    nextPageToken = ''
    pageNumber = 0
    while (nextPageToken!= 'end' or pageNumber == 0):
        pageNumber += 1
        response = service.commentThreads().list(
            part=part_string,
            videoId=videoId,
            maxResults=100,
            pageToken=nextPageToken,
        ).execute()
        nextPageToken = response.get('nextPageToken','end')
        # Store the current page of results
        responses = responses + response['items']
    return responses

def getRecentChannelVids(channel_ids: list, recent_x: int) -> list:
    """Return list of channel vids ids (no API needed)

    Args:
        channel_ids (list): List of channel ids
        recent_x (int): x recents videos to ingest

    Returns:
        list: dictionary of channel id and their list of video url
        {
            channelId: 'channelId',
            videoIds: ['videoUrl1', 'videoUrl2' etc,...]
        }
    """
    result = []
    for channel_id in channel_ids:
        url = "https://www.youtube.com/channel/" + channel_id + '/videos'
        c = Channel(url)
        result.append({
            'channelId': channel_id,
            'videoUrls': [videoUrl[32:] for videoUrl in c.video_urls[:recent_x]]
        })
    return result


def getRelatedVideoIds(relatedToVideoId: str) -> list:
    maxResults = 50
    pageCount = 0
    videoIdsList = []
    response = {}

    while (response.get('nextPageToken') is not None or pageCount == 0):
        response = service.search().list(
            part='id',
            relatedToVideoId=relatedToVideoId,
            maxResults=maxResults,
            pageToken=response.get('nextPageToken'),
            type='video'
        ).execute()
        pageCount += 1
        # Store the current page of results
        for item in response['items']:
            videoIdsList.append(item['id']['videoId'])

    relatedVideoIds = list(set(videoIdsList))

    return relatedVideoIds


def getVideoListDetails(VideoIds: list) -> bool:
    resultsChunks = [VideoIds[i:i + 50]
                     for i in range(0, len(VideoIds), 50)]
    for result in resultsChunks:
        getVideoDetail(",".join(result))
    return True


def queryKeyword(keyword: str, seedId: str = None, order: str = 'relevance', videoCaption: str = "any", pageLimit=2) -> list:
    """Search youtube based on youtube search API
    Source: https://developers.google.com/youtube/v3/docs/search/list

    Args:
        keyword (str): query
        order (str, optional): The order parameter specifies the method that will be used to order resources in the API response. Defaults to 'relevance'.
        Acceptable values are:
            date: Resources are sorted in reverse chronological order based on the date they were created.
            rating: Resources are sorted from highest to lowest rating.
            relevance: Resources are sorted based on their relevance to the search query. This is the default value for this parameter.
            title: Resources are sorted alphabetically by title.
            videoCount: Channels are sorted in descending order of their number of uploaded videos.
            viewCount: Resources are sorted from highest to lowest number of views. For live broadcasts, videos are sorted by number of concurrent viewers while the broadcasts are ongoing.
        videoCaption (str, optional): The videoCaption parameter indicates whether the API should filter video search results based on whether they have captions. If you specify a value for this parameter, you must also set the type parameter's value to video.
        Defaults to "any".
        Acceptable values are:
            any: Do not filter results based on caption availability.
            closedCaption: Only include videos that have captions.
            none: Only include videos that do not have captions.
        pageLimit (int, optional): 50 max return per page. Defaults to 2.

    Returns:
        list: list of video ids
    """
    maxResults = 50
    videoIdsList = [seedId]
    response = {}
    query = keyword
    pageCount = 0

    if videoCaption == "Include":
        videoCaption = 'any'
    elif videoCaption == "Exclude":
        videoCaption = 'closedCaption'

    while (response.get('nextPageToken') is not None or pageCount == 0) and pageCount != pageLimit:
        response = service.search().list(
            part='id,snippet',
            maxResults=maxResults,
            q=query,
            pageToken=response.get('nextPageToken'),
            type='video',
            order=order,
            videoCaption=videoCaption
        ).execute()
        pageCount += 1
        print("Next page found, downloading", response.get('nextPageToken'))
        # Store the current page of results
        for item in response['items']:
            videoIdsList.append(item['id']['videoId'])

    searchVideoIDs = list(set(videoIdsList))
    return searchVideoIDs


def queryChannelVidIds(channelId: str, limit=2):
    maxResults = 50
    response = {}
    pageCount = 0
    while (response.get('nextPageToken') is not None or pageCount == 0) and pageCount != limit:
        response = service.search().list(
            part='snippet',
            maxResults=maxResults,
            order='date',
            channelId=channelId,
            pageToken=response.get('nextPageToken')
        ).execute()
        pageCount += 1
        print("Next page found, downloading", response.get('nextPageToken'))

    return response
