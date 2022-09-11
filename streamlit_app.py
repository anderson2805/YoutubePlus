from io import BytesIO

import numpy as np
import pandas as pd
import streamlit as st
from pytube import Channel, YouTube
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
from youtube_transcript_api import YouTubeTranscriptApi
#from streamlit_custom_slider import st_custom_slider
import src.feature as feature
import src.ingestion as ingestion
import src.process as process

try:
    from src.semantic_similarity import embed
except:
    from src.semantic_similarity_lite import embed

from src.service import check_api

st.set_page_config(
    page_title="Youtube+",
    page_icon="⏩",

)

st.header('✨Youtube: Video Originality')
st.write('Enhance discovery of Youtube contents')

st.markdown(
    """
<style>
.streamlit-expanderHeader {
    font-size: x-large;
    font-weight: bold;
}
</style>
""",
    unsafe_allow_html=True,
)


@st.experimental_memo(suppress_st_warning=True)
def to_excel(dfs: dict, captionDf: pd.DataFrame, processeddf: pd.DataFrame = pd.DataFrame(), channelDfDict: dict = {}, commentSummarisedDfDict: dict = {}, commentsResultDfDict: dict = {}) -> BytesIO:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        if(len(pd.DataFrame()) != 0):
            processeddf.to_excel(writer, sheet_name='similarity')
        dfs['videoDf'].to_excel(writer, sheet_name='stats')
        dfs['videoLocDf'].to_excel(writer, sheet_name='loc')
        dfs['videoHashtagsDf'].to_excel(writer, sheet_name='hashtags')
        dfs['videoTopicsDf'].to_excel(writer, sheet_name='topics')
        dfs['videoTagsDf'].to_excel(writer, sheet_name='tags')
        captionDf.to_excel(writer, sheet_name='captions')
        for df_name, df in channelDfDict.items():
            df.to_excel(writer, sheet_name=df_name)
        if(len(commentSummarisedDfDict) != 0):
            for df_name, df in commentSummarisedDfDict.items():
                df.to_excel(writer, sheet_name=df_name)
        if(len(commentsResultDfDict) != 0):
            for df_name, df in commentsResultDfDict.items():
                df.to_excel(writer, sheet_name=df_name)
    processed_data = output.getvalue()

    return processed_data


def create_gb(df: pd.DataFrame, linkColumn: str = "", selection: bool = False):
    gb = GridOptionsBuilder.from_dataframe(df)
    cell_renderer = JsCode("""
    function(params) {return `<a href=${params.value} target="_blank">${params.value}</a>`}
    """)
    gb.configure_side_bar()
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_grid_options(domLayout='normal')
    if(selection):
        gb.configure_selection('single', use_checkbox=False,)
    if(linkColumn != ""):
        gb.configure_column(linkColumn, cellRenderer=cell_renderer)
    gb.configure_default_column(
        groupable=True, value=True, enableRowGroup=True, aggFunc="sum", editable=False)
    return gb


with st.expander(label='Similar Video', expanded=True):

    st.write("""
    As a way of determining the originality of a video, it can be helpful to look for semantically similar videos.
    Start by entering the video link you wish to search for semantically similar videos and your Google API key for Streamlit.
    
    Detailed instructions on obtaining the API key and analysing the data can be found in the [documentation](https://anderson2805.github.io/yt_support/)
    """)

    def api_callback():
        if len(st.session_state.api_input) < 39:
            st.warning("API key too short")
        elif check_api(st.session_state.api_input) == "API access successful":
            st.success(check_api(st.session_state.api_input))
        else:
            st.warning(check_api(st.session_state.api_input))

    ingestion.API_KEY = st.text_input(
        label='API', placeholder='YOUR_API_KEY',
        help='Instruction to obtain API Key: https://developers.google.com/youtube/v3/getting-started',
        on_change=api_callback, max_chars=39, key='api_input')

    ingestion.service = ingestion.create_yt_service(ingestion.API_KEY)

    tabMain1, tabMain2 = st.tabs(['Seed Videos', 'List of Videos'])
    with tabMain1:
        col1, col2 = st.columns([3, 1])
        with col1:
            video_url = st.text_input(
                'Video URL', placeholder='https://www.youtube.com/watch?v=xxxxxxxxx',
                help='Video must contain English closed captioning')
        with col2:
            st.write("##")
            load_example = st.button(
                'or Load Example', key='load_example', disabled=(True or len(video_url) >= 1))

        if load_example == True:
            st.session_state['example'] = pd.read_excel(
                'example/iphone14.xlsx', sheet_name=None)
            videoProcessedDf = pd.DataFrame(st.session_state['example']['similarity'])[[
                'Similarity %', 'Title', 'Views', 'Likes', 'Comments', 'Video URL']]
            st.session_state['videoProcessedDf'] = videoProcessedDf
            video_url = "https://www.youtube.com/watch?v=" + \
                st.session_state['example']['similarity'].videoId[0]
            st.session_state.commentsResultDfDict = {your_key: st.session_state['example'].get(
                your_key) for your_key in ['Comments', 'Comments Author', 'Comments Links', 'Comments Hashtags']}
            
        if len(video_url) >= 28:
            st.video(video_url)
            video_info = YouTube(video_url)
            video_id = video_info.video_id
            channel_id = video_info.channel_id
            try:
                YouTubeTranscriptApi.list_transcripts(video_id)
            except:
                st.warning(
                    'Please choose another video! Fail to load video caption needed for similarity check.')
            video_title = st.text_input(label='Title', value=video_info.title)

            col2_1, col2_2 = st.columns([1, 1])
            with col2_1:
                st.text_area(label="Raw Description",
                             value=video_info.description, disabled=True, height=300)
            with col2_2:
                processed_Description = st.text_area(
                    label="Processed Description (beta)", value=process.process_description(video_info.description), height=300, help='Removed call-to-action texts (beta)')

            keywords_extracted = feature.extractKeywords(
                video_title + ". " + processed_Description)
            st.write('Suggested Query Keywords: ' +
                     ", ".join(keywords_extracted))

            selected_keywords = st.text_input(
                label='Query Keywords', value=keywords_extracted[0], help='Keywords used to query for more videos on Youtube', key='selected_keywords')

            query_max = st.slider(
                label='Number of videos to query', min_value=100, max_value=250, value=100, step=50, key="slider1")

            col1, col2, col3 = st.columns(3)

            with col1:
                queryOrder = st.selectbox(
                    'API Search Ordering', index=0, options=('Relevance', 'Date', 'Rating', 'Title', 'Video Count', 'View Count'), help="https://developers.google.com/youtube/v3/docs/search/list#order")
            with col2:
                caption = st.radio("Non-caption videos", ('Include', 'Exclude'), index=1,
                                   help='Not including non-caption video will speed up processing time and reduce API costing')
            with col3:
                related = st.radio(
                    "Related videos",
                    ('Include', 'Exclude'), help='Utalising Youtube Related API: https://developers.google.com/youtube/v3/docs/search/list, it can be related based on music used in inputed video')
            # with col4:
            #     channelSel = st.radio(
            #         "Channels data",
            #         ('Include', 'Exclude'), index=0, help='Utalising Youtube Related API: https://developers.google.com/youtube/v3/docs/channels/list, include all videos channel information')

            download = st.button(label='Call data from YT APIs', disabled=(check_api(
                st.session_state.api_input) != "API access successful"), help=str(check_api(st.session_state.api_input)), key="download")
            st.write('Estimated time to collect: %i minutes' %
                     (query_max/50*2.5))

            if(st.session_state.download):
                with st.spinner(text='Collecting queried video info (title, description, captions, etc.)...'):
                    query_vid_ids = ingestion.queryKeyword(
                        selected_keywords, video_id, queryOrder.lower(), caption, pageLimit=st.session_state.slider1//50)
                    videoList, videoLocList, videoHashtagsList, videoCaptionList, videoTopicsList, videoTagsList = process.processVideoIds(
                        query_vid_ids)
                if(related == 'Include'):
                    with st.spinner(text='Collecting related video info (title, description, captions, etc.)...'):
                        related_vid_ids = ingestion.getRelatedVideoIds(
                            video_id)
                        videoList2, videoLocList2, videoHashtagsList2, videoCaptionList2, videoTopicsList2, videoTagsList2 = process.processVideoIds(
                            related_vid_ids)
                        videoList.extend(videoList2)
                        videoLocList.extend(videoLocList2)
                        videoHashtagsList.extend(videoHashtagsList2)
                        videoCaptionList.extend(videoCaptionList2)
                        videoTopicsList.extend(videoTopicsList2)
                        videoTagsList.extend(videoTagsList2)
                with st.spinner(text='Collecting channel info (channel name, description, creation date, etc.)...'):
                    channelIds = pd.DataFrame(videoList)['channelId'].unique()
                    channelDfs = process.processChannelIds(channelIds)
                with st.spinner(text='Calculating similarity (based on english captions)...'):
                    videoDfs = process.videoDetails_df(
                        videoList, videoLocList, videoHashtagsList, videoCaptionList, videoTopicsList, videoTagsList)

                    videoDf = videoDfs['videoDf']
                    videoCaptionDf = videoDfs['videoCaptionDf']

                    videoCaptionDf['embedding'] = embed(
                        videoCaptionDf['embedding'])

                    videoCaptionDf['Similarity %'] = np.inner(videoCaptionDf[videoCaptionDf.index == video_id].embedding.values[0],
                                                              videoCaptionDf['embedding'].to_list())

                    videoProcessedDf = videoDf.join(
                        videoCaptionDf, how='outer')
                    videoProcessedDf = videoProcessedDf[~videoProcessedDf.index.duplicated(
                    )]
                    videoProcessedDf['Video URL'] = "https://www.youtube.com/watch?v=" + \
                        videoProcessedDf.index
                    videoProcessedDf = videoProcessedDf.join(channelDfs['channelInfo'].set_index(
                        'channelId'), rsuffix='_channel', on='channelId')
                    videoProcessedDf = videoProcessedDf[[
                        'Similarity %', 'title', 'viewCount', 'likeCount', 'commentCount', 'Video URL', 'Channel Name', 'Creation Date', 'Subscribers']]
                    videoProcessedDf.rename(
                        columns={"title": "Title", "viewCount": "Views", "likeCount": "Likes", "commentCount": "Comments"}, inplace=True)
                    videoProcessedDf.sort_values(
                        by=['Similarity %'], ascending=False, inplace=True)
                    cols = ['Views', "Likes", "Comments"]
                    videoProcessedDf[cols] = videoProcessedDf[cols].apply(
                        pd.to_numeric, downcast="integer", errors='coerce')
                    videoDf = videoDf.join(
                        videoProcessedDf, how='left', on='videoId')
                    videoDf.drop(['Title', 'Views', 'Likes', 'Channel Name', 'Creation Date', 'Subscribers',
                                  'Comments'], axis=1, inplace=True)
                    videoDf = videoDf[~videoDf.index.duplicated()]
                    videoDf.sort_values(
                        by=['Similarity %'], ascending=False, inplace=True)
                    videoDf['seedvideo'] = videoDf.index == video_id
                    videoDf['seedchannel'] = videoDf.channelId == channel_id
                    videoDfs['videoDf'] = videoDf
                    videoProcessedDf['Similarity %'] = (
                        videoProcessedDf['Similarity %']*100).round(1)
                    st.session_state['videoProcessedDf'] = videoProcessedDf
                    st.session_state['videoDfs'] = videoDfs
                    st.session_state['videoCaptionDf'] = videoCaptionDf
                    st.session_state['channelDfs'] = channelDfs
                st.success('Done!')
                # videoProcessDf = videoDfs['videoDf'].join(
                #     videoDfs['videoEmbedDf'], how='other')
            if (st.session_state.get('videoProcessedDf') is not None):
                if load_example == False:
                    videoProcessedDf = st.session_state['videoProcessedDf']
                    videoDfs = st.session_state.get('videoDfs')
                    videoCaptionDf = st.session_state.get('videoCaptionDf')
                    channelDfs = st.session_state['channelDfs']
                gb = GridOptionsBuilder.from_dataframe(videoProcessedDf)
                cell_renderer = JsCode("""
                function(params) {return `<a href=${params.value} target="_blank">${params.value}</a>`}
                """)
                gb.configure_side_bar()
                gb.configure_pagination(paginationAutoPageSize=True)
                gb.configure_grid_options(domLayout='normal')
                gb.configure_selection('multiple', use_checkbox=True,)
                gb.configure_column("Video URL", cellRenderer=cell_renderer)
                gb.configure_default_column(
                    groupable=True, value=True, enableRowGroup=True, aggFunc="sum", editable=False)
                # gb.configure_column("Description", editable = True)
                gridOptions = gb.build()
                grid_response = AgGrid(
                    videoProcessedDf, gridOptions, update_mode=GridUpdateMode.MANUAL, enable_enterprise_modules=True, allow_unsafe_jscode=True)
    #            st.warning('Result will be cleared when data downloaded.')
                if st.session_state['load_example'] == False:
                    st.session_state['export'] = to_excel(
                        videoDfs, videoCaptionDf, videoProcessedDf, channelDfs)
                else:
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        for df_name, df in st.session_state['example'].items():
                            df.to_excel(
                                writer, sheet_name=df_name, index=False)
                    st.session_state.export = output.getvalue()
                response = grid_response['selected_rows']

                comments_btn = st.button("Load %s Comments of %s Video Selected" % (sum(d.get(
                    'Comments', 0) for d in response), len(response)), disabled=len(response) == 0)
                if(comments_btn):
                    # grid_response.update()
                    commentsResultDfDict = process.processVideosComments([row['Video URL'].split('=')[-1]
                                                                          for row in grid_response['selected_rows']])
                    st.session_state.commentsResultDfDict = commentsResultDfDict
                dl_btn_label = "📥Download Videos + Channels Data"

    with tabMain2:
        videoIds = st.text_area(
            "Enter Video Ids seperated by comma (,)").replace('\n', "").split(',')
        start = st.button('Call YT API for data')
        if start:
            videoList, videoLocList, videoHashtagsList, videoCaptionList, videoTopicsList, videoTagsList = process.processVideoIds(
                videoIds)

            videoDfs = process.videoDetails_df(
                videoList, videoLocList, videoHashtagsList, videoCaptionList, videoTopicsList, videoTagsList)
            channelIds = pd.DataFrame(videoList)['channelId'].unique()
            channelDfs = process.processChannelIds(channelIds)
            videoCaptionDf = videoDfs['videoCaptionDf']
            st.session_state.videoDfs = videoDfs
            st.session_state.videoCaptionDf = videoDfs['videoCaptionDf']
            st.session_state.videoProcessedDf = pd.DataFrame()
            st.session_state.channelDfs = channelDfs
            commentsResultDfDict = process.processVideosComments(videoIds)

            st.session_state.commentsResultDfDict = commentsResultDfDict

    if(st.session_state.get('commentsResultDfDict') is not None):
        dl_btn_label = "📥Download Videos + Channels + Comments Data"
        commentsResultDfDict = st.session_state.commentsResultDfDict
        commentSummarisedDfDict = process.summarisedComments(
            commentsResultDfDict)
        tab1, tab2, tab3 = st.tabs(
            ["Comments Summary 🗯️", "Links 🔗", "Hashtags #️⃣"])

        with tab1:
            gb1 = create_gb(
                commentSummarisedDfDict['Comments Summary 🗯️'], selection=True)
            gb1.configure_default_column(
                groupable=True, value=True, enableRowGroup=True, aggFunc="sum", editable=False)
            # gb.configure_column("Description", editable = True)
            gridOptions1 = gb1.build()
            grid_response1 = AgGrid(
                commentSummarisedDfDict['Comments Summary 🗯️'], gridOptions1, update_mode=GridUpdateMode.SELECTION_CHANGED, enable_enterprise_modules=True, allow_unsafe_jscode=False, key='commentSummary')

            if(grid_response1.get('selected_rows')is not None):
                if(grid_response1.get('selected_rows') != []):
                    st.dataframe(commentsResultDfDict['Comments'].loc[commentsResultDfDict['Comments']['authorChannelId'] == grid_response1['selected_rows']
                                                        [0]['authorChannelId']][['commentId', 'videoId', 'textOriginal', 'publishedAt', 'Account age when commenting (days)']])
        if(commentSummarisedDfDict.get('Links 🔗') is not None):
            with tab2:
                gb2 = create_gb(
                    commentSummarisedDfDict['Links 🔗'].reset_index(), linkColumn='cleanLink')
                gb2.configure_default_column(
                    groupable=True, value=True, enableRowGroup=True, aggFunc="sum", editable=False)
                # gb.configure_column("Description", editable = True)
                gridOptions2 = gb2.build()
                grid_response2 = AgGrid(
                    commentSummarisedDfDict['Links 🔗'].reset_index(), gridOptions2, update_mode=GridUpdateMode.SELECTION_CHANGED, enable_enterprise_modules=True, allow_unsafe_jscode=True, key='commentLinks')
        if(commentSummarisedDfDict.get('Hashtags #️⃣') is not None):
            with tab3:
                gb3 = create_gb(
                    commentSummarisedDfDict['Hashtags #️⃣'].reset_index())
                gb3.configure_default_column(
                    groupable=True, value=True, enableRowGroup=True, aggFunc="sum", editable=False)
                # gb.configure_column("Description", editable = True)
                gridOptions3 = gb3.build()
                grid_response3 = AgGrid(
                    commentSummarisedDfDict['Hashtags #️⃣'].reset_index(), gridOptions3, update_mode=GridUpdateMode.SELECTION_CHANGED, enable_enterprise_modules=True, allow_unsafe_jscode=False, key='commentHashtags')

        if st.session_state['load_example'] == False:
            videoDfs = st.session_state.videoDfs
            videoCaptionDf = st.session_state.videoCaptionDf
            videoProcessedDf = st.session_state.get('videoProcessedDf', pd.DataFrame())
            channelDfs = st.session_state.channelDfs
            st.session_state['export'] = to_excel(
                videoDfs, videoCaptionDf, videoProcessedDf, channelDfs, commentSummarisedDfDict, commentsResultDfDict)
        else:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                for df_name, df in st.session_state['example'].items():
                    df.to_excel(writer, sheet_name=df_name, index=False)
            st.session_state.export = output.getvalue()
        if(st.session_state.get('export') is not None):
            st.download_button(
                label=dl_btn_label,
                data=st.session_state.export,
                file_name='YTPlus_SimilarVideos_data.xlsx',
                help='Include full data of video stats, locations, hashtags, captions and embeddings.'
            )
    st.write("Credit to [KeyBERT](https://maartengr.github.io/KeyBERT/index.html) for keywords extraction and [Google's Universal Sentence Encoder](https://www.tensorflow.org/hub/tutorials/semantic_similarity_with_tf_hub_universal_encoder) for caption embedding")


# with st.expander(label='Channel Suggestion', expanded=False):
#     st.write("""
#     Suggest channels that produce similar type of contents.""")

#     channelUrl = st.text_input(label='Channel URL', key='channelUrl')
