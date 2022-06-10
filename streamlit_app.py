from io import BytesIO
import numpy as np
import pandas as pd
import streamlit as st
from pytube import Channel, YouTube
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

import src.feature as feature
import src.ingestion as ingestion
import src.process as process
from src.semantic_similarity import embed
from src.service import check_api

st.set_page_config(
    page_title="Youtube+",
    page_icon="⏩",

)

st.header('✨Youtube+')
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


@st.cache
def to_excel(dfs: dict, captionDf: pd.DataFrame, processeddf: pd.DataFrame) -> BytesIO:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        processeddf.to_excel(writer, sheet_name='similarity')
        dfs['videoDf']['publishedAt'] = dfs['videoDf']['publishedAt']
        dfs['videoDf']['recordingDate'] = dfs['videoDf']['recordingDate']
        dfs['videoDf'].to_excel(writer, sheet_name='stats')
        dfs['videoLocDf'].to_excel(writer, sheet_name='loc')
        dfs['videoHashtagsDf'].to_excel(writer, sheet_name='hashtags')
        captionDf.to_excel(writer, sheet_name='captions')
    processed_data = output.getvalue()
    return processed_data


with st.expander(label='Similar Video', expanded=True):

    st.write("""
    Finding semantic similar videos can help determine how original a video is.
    Enter video link that you like to look for semantically similar videos""")

    def api_callback():
        if(len(st.session_state.api_input) < 39):
            st.warning("API key too short")
        elif(check_api(st.session_state.api_input) == "API access successful"):
            st.success(check_api(st.session_state.api_input))
        else:
            st.warning(check_api(st.session_state.api_input))

    ingestion.API_KEY = st.text_input(
        label='API', placeholder='YOUR_API_KEY',
        help='Instruction to obtain API Key: https://developers.google.com/youtube/v3/getting-started', on_change=api_callback, max_chars=39, key='api_input')

    ingestion.service = ingestion.create_yt_service(ingestion.API_KEY)

    video_url = st.text_input(
        'Video URL', placeholder='https://www.youtube.com/watch?v=xxxxxxxxx')

    if(len(video_url) >= 43):
        st.video(video_url)
        video_info = YouTube(video_url)
        video_id = video_info.video_id
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
        st.write('Suggested Query Keywords: ' + ", ".join(keywords_extracted))

        selected_keywords = st.text_input(
            label='Query Keywords', value=keywords_extracted[0], help='Keywords used to query for more videos on Youtube', key='selected_keywords')

        query_max = st.slider(
            label='Number of pages to query (50 videos per page)', min_value=2, max_value=20, value=2)

        related = st.radio(
            "Include related videos",
            ('Yes', 'No'), help='Utalising Youtube Related API: https://developers.google.com/youtube/v3/docs/search/list, it can be related based on music used in inputed video')

        download = st.button(label='Call data from YT APIs', disabled=(check_api(
            st.session_state.api_input) != "API access successful"), help=str(check_api(st.session_state.api_input)))
        st.write('Estimated time to collect: %i minutes'%(query_max*2.5))
        if(download):
            with st.spinner(text='Collecting queried video info (title, description, captions, etc.)...'):
                query_vid_ids = ingestion.queryKeyword(
                    selected_keywords, query_max)
                videoList, videoLocList, videoHashtagsList, videoCaptionList = process.processVideoIds(
                    query_vid_ids)
                videoDfs = process.videoDetails_df(
                    videoList, videoLocList, videoHashtagsList, videoCaptionList)
            if(related == 'Yes'):
                with st.spinner(text='Collecting related video info (title, description, captions, etc.)...'):
                    related_vid_ids = ingestion.getRelatedVideoIds(video_id)
                    videoList2, videoLocList2, videoHashtagsList2, videoCaptionList2 = process.processVideoIds(
                        related_vid_ids)
                    videoList.extend(videoList2)
                    videoLocList.extend(videoLocList2)
                    videoHashtagsList.extend(videoHashtagsList2)
                    videoCaptionList.extend(videoCaptionList2)
            with st.spinner(text='Calculating similarity (based on english captions)...'):
                videoDfs = process.videoDetails_df(
                    videoList, videoLocList, videoHashtagsList, videoCaptionList)

                videoDf = videoDfs['videoDf']
                videoCaptionDf = videoDfs['videoCaptionDf']
                videoCaptionDf['embedding'] = embed(
                    videoCaptionDf['embedding'])

                videoCaptionDf['Similarity'] = np.inner(videoCaptionDf[videoCaptionDf.index == video_id].embedding.values[0],
                                                        videoCaptionDf['embedding'].to_list())

                videoProcessedDf = videoDf.join(videoCaptionDf, how='outer')
                videoProcessedDf['Video URL'] = "https://www.youtube.com/watch?v=" + \
                    videoProcessedDf.index
                videoProcessedDf = videoProcessedDf[[
                    'Similarity', 'title', 'viewCount', 'Video URL']]
                videoProcessedDf.rename(
                    columns={"title": "Title", "viewCount": "View Count"}, inplace=True)
                videoProcessedDf.sort_values(
                    by=['Similarity'], ascending=False, inplace=True)
                videoProcessedDf['View Count'] = pd.to_numeric(
                    videoProcessedDf['View Count'], downcast='float', errors='raise').astype('Int64')
                videoProcessedDf['Similarity'] = videoProcessedDf['Similarity'].map(
                    "{:.1%}".format)
                videoProcessedDf.drop_duplicates(inplace = True)
            st.success('Done!')
            # videoProcessDf = videoDfs['videoDf'].join(
            #     videoDfs['videoEmbedDf'], how='other')
            gb = GridOptionsBuilder.from_dataframe(videoProcessedDf)

            gb.configure_side_bar()
            gb.configure_pagination(paginationAutoPageSize=True)
            gb.configure_grid_options(domLayout='normal')
            #gb.configure_selection('single', use_checkbox=False)
            gb.configure_default_column(
                groupable=True, value=True, enableRowGroup=True, aggFunc="sum", editable=False)
            # gb.configure_column("Description", editable = True)
            gridOptions = gb.build()

            grid_response = AgGrid(
                videoProcessedDf, gridOptions, update_mode=GridUpdateMode.SELECTION_CHANGED, enable_enterprise_modules=True)

            st.warning('Result will be cleared when data downloaded.')
            st.download_button(
                label="📥Download Data",
                data=to_excel(videoDfs, videoCaptionDf, videoProcessedDf),
                file_name='YTPlus_SimilarVideos_data.xlsx',
                help='Include full data of video stats, locations, hashtags, captions and embeddings.'
            )
