from src.service import create_yt_service

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
    part_string = 'snippet,brandingSettings,statistics,topicDetails'

    response = service.channels().list(
        part=part_string,
        id=channel_ids,
        maxResults=50
    ).execute()

    return response


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


def queryKeyword(keyword: str, pageLimit=15):
    maxResults = 50
    videoIdsList = []
    response = {}
    query = keyword
    pageCount = 0
    while (response.get('nextPageToken') is not None or pageCount == 0) and pageCount != pageLimit:
        response = service.search().list(
            part='id,snippet',
            maxResults=maxResults,
            q=query,
            pageToken=response.get('nextPageToken'),
            type='video'
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
