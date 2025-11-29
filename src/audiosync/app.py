"""
AudioSync Streamlit Web アプリケーション

Streamlitを使用したAudioSyncのWebインターフェース
"""

import streamlit as st
import os
import pandas as pd
from datetime import datetime

from database import Database
from logger import setup_logger

logger = setup_logger(__name__)

# ページ設定
st.set_page_config(
    page_title="AudioSync",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# セッション状態の初期化
if 'db' not in st.session_state:
    st.session_state.db = Database()
    logger.info("Database initialized in session state")

db = st.session_state.db


# ==================== ヘッダー ====================
st.title("🎵 AudioSync Web版")
st.markdown("音楽ファイル管理・同期システム")

# ==================== サイドバー ====================
with st.sidebar:
    st.header("⚙️ 操作パネル")
    
    # デ��タベース情報
    st.markdown("---")
    st.subheader("📊 データベース情報")
    all_files = db.get_all_audio_files()
    sync_files = db.get_all_audio_files(sync_only=True)
    playlists = db.get_all_playlists()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("総曲数", len(all_files))
        st.metric("プレイリスト数", len(playlists))
    with col2:
        st.metric("同期対象", len(sync_files))
        st.metric("未同期", len(all_files) - len(sync_files))
    
    # タスク実行ボタン
    st.markdown("---")
    st.subheader("🔧 タスク実行")
    
    col_scan1, col_scan2 = st.columns([3, 1])
    with col_scan1:
        scan_btn = st.button("🔍 音楽ファイルをスキャン", use_container_width=True)
    with col_scan2:
        update_all = st.checkbox("全更新", help="変更がないファイルもメタデータを再取得します")

    if scan_btn:
        try:
            from audio_scan import scan_audio_files
            
            # プログレスバー表示用のプレースホルダー
            progress_placeholder = st.empty()
            status_placeholder = st.empty()
            
            def progress_callback(current, total, message):
                if total > 0:
                    progress_placeholder.progress(current / total, text=message)
                status_placeholder.info(message)
            
            # スキャン実行
            result = scan_audio_files(db, progress_callback, update_all=update_all)
            
            # 結果表示
            progress_placeholder.empty()
            status_placeholder.empty()
            st.success(
                f"✅ スキャン完了\n"
                f"- 追加: {result['added']}件\n"
                f"- 更新: {result['updated']}件\n"
                f"- スキップ: {result.get('skipped', 0)}件\n"
                f"- 削除(見つからない): {result.get('deleted', 0)}件\n"
                f"- 合計: {result['total']}件"
            )
            st.rerun()
            
        except Exception as e:
            st.error(f"スキャンエラー: {str(e)}")
            logger.error(f"Scan error: {e}", exc_info=True)
    
    if st.button("🔄 同期を実行", use_container_width=True):
        try:
            from audio_synchronize import synchronize_files
            
            # プログレスバー表示用のプレースホルダー
            progress_placeholder = st.empty()
            status_placeholder = st.empty()
            
            # ログ表示エリア
            log_expander = st.expander("実行ログ", expanded=True)
            with log_expander:
                log_area = st.empty()
            
            logs = []
            
            def progress_callback(current, total, message):
                if total > 0:
                    progress_placeholder.progress(current / total, text=message)
                status_placeholder.info(message)
            
            def log_callback(message):
                logs.append(message.rstrip())
                # 最新の50行を表示
                log_area.code("\n".join(logs[-50:]))
            
            # 同期実行
            result = synchronize_files(db, progress_callback, log_callback=log_callback)
            
            # 結果表示
            progress_placeholder.empty()
            status_placeholder.empty()
            st.success(f"✅ 同期完了: {result['method'].upper()}で同期しました")
            
        except Exception as e:
            st.error(f"同期エラー: {str(e)}")
            logger.error(f"Sync error: {e}", exc_info=True)
    
    # データベースリセット
    st.markdown("---")
    if st.button("♻️ DBリセット", use_container_width=True, type="secondary"):
        if st.button("本当にリセットしますか？", type="secondary"):
            # TODO: 実装
            st.warning("この機能はまだ実装されていません")


# ==================== メインコンテンツ ====================

# タブで画面を分ける
tab1, tab2, tab3 = st.tabs(["🎵 音楽リスト", "📋 プレイリスト", "⚙️ 設定"])

# ==================== タブ1: 音楽リスト ====================
with tab1:
    st.header("音楽ファイル一覧")
    
    # フィルタ
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        search_query = st.text_input("🔎 検索（タイトル、アーティスト、アルバム）", "")
    with col2:
        filter_sync = st.selectbox(
            "同期状態",
            ["全て", "同期対象のみ", "未同期のみ"]
        )
    with col3:
        st.write("")  # スペーサー
        if st.button("🔄 更新", use_container_width=True):
            st.rerun()
    
    # 音楽ファイル一覧を取得
    if filter_sync == "同期対象のみ":
        files = db.get_all_audio_files(sync_only=True)
    else:
        files = db.get_all_audio_files(sync_only=False)
    
    # 検索フィルタ適用
    if search_query:
        search_lower = search_query.lower()
        files = [
            f for f in files
            if (f.get('title') and search_lower in f['title'].lower()) or
               (f.get('artist') and search_lower in f['artist'].lower()) or
               (f.get('album') and search_lower in f['album'].lower())
        ]
    
    # 未同期フィルタ
    if filter_sync == "未同期のみ":
        files = [f for f in files if not f.get('sync')]
    
    st.write(f"表示件数: {len(files)}件")
    
    # テーブル表示
    if files:
        # DataFrameに変換
        df = pd.DataFrame(files)
        # IDをインデックスに設定（編集時のキーとして使用）
        df.set_index('id', inplace=True)
        
        # 表示列を選択
        display_columns = ['sync', 'msg', 'title', 'artist', 'album', 'track_num', 'codec', 'filename', 'filepath_from', 'added_date', 'update_date']
        display_df = df[display_columns].copy()
        
        # sync列をbool型に変換
        display_df['sync'] = display_df['sync'].astype(bool)
        
        # 選択列を追加（初期値はすべてFalse）
        display_df.insert(0, '選択', False)
        
        # データエディタで表示（戻り値を受け取る）
        edited_df = st.data_editor(
            display_df,
            key="music_list_editor",
            column_config={
                "選択": st.column_config.CheckboxColumn(
                    "選択",
                    help="プレイリストに追加する曲を選択",
                    default=False,
                    width="small"
                ),
                "sync": st.column_config.CheckboxColumn(
                    "同期",
                    help="チェックすると同期対象になります",
                    default=False,
                    width="small"
                ),
                "msg": st.column_config.TextColumn("Msg", width="small"),
                "title": st.column_config.TextColumn("タイトル", width="medium"),
                "artist": st.column_config.TextColumn("アーティスト", width="medium"),
                "album": st.column_config.TextColumn("アルバム", width="medium"),
                "track_num": st.column_config.TextColumn("#", width="small"),
                "codec": st.column_config.TextColumn("形式", width="small"),
                "filename": st.column_config.TextColumn("ファイル名", width="large"),
                "filepath_from": st.column_config.TextColumn("ファイルパス", width="large"),
                "added_date": st.column_config.TextColumn("追加日時", width="medium"),
                "update_date": st.column_config.TextColumn("更新日時", width="medium"),
            },
            disabled=['msg', 'title', 'artist', 'album', 'track_num', 'codec', 'filename', 'filepath_from', 'added_date', 'update_date'],
            use_container_width=True,
            height=600
        )
        
        # 選択されているファイルIDを取得
        selected_files = edited_df[edited_df['選択']].index.tolist()
        
        # sync列の変更チェック
        has_sync_changes = not (edited_df['sync'] == display_df['sync']).all()
        
        # 操作ボタン
        col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 6])
        
        with col_btn1:
            # sync変更の保存ボタン
            if st.button("💾 同期設定を保存", disabled=not has_sync_changes, type="primary" if has_sync_changes else "secondary"):
                sync_changes = edited_df['sync'] != display_df['sync']
                if sync_changes.any():
                    changed_ids = sync_changes[sync_changes].index.tolist()
                    for file_id in changed_ids:
                        new_sync_value = edited_df.loc[file_id, 'sync']
                        db.update_sync_status(int(file_id), bool(new_sync_value))
                    st.success(f"{len(changed_ids)}件の同期設定を保存しました")
                    st.rerun()
        
        with col_btn2:
            # 選択解除ボタン
            if st.button("⬜ 選択解除", disabled=len(selected_files) == 0):
                st.rerun()
        
        # 選択したファイルに対する操作
        if len(selected_files) > 0:
            st.markdown("---")
            st.write(f"**選択中: {len(selected_files)}曲**")
            
            tab_add, tab_del = st.tabs(["➕ プレイリストに追加", "🗑️ 削除"])
            
            with tab_add:
                playlists = db.get_all_playlists()
                if playlists:
                    col_pl1, col_pl2 = st.columns([3, 1])
                    with col_pl1:
                        playlist_names = [p['name'] for p in playlists]
                        target_playlist = st.selectbox(
                            "追加先プレイリスト",
                            playlist_names,
                            key="target_playlist_for_add"
                        )
                    with col_pl2:
                        st.write("")  # スペーサー
                        if st.button("追加実行", type="primary", key="btn_add_playlist"):
                            playlist = next((p for p in playlists if p['name'] == target_playlist), None)
                            if playlist:
                                db.add_to_playlist_many(playlist['id'], selected_files)
                                st.success(f"{len(selected_files)}曲を「{target_playlist}」に追加しました")
                                st.rerun()
                else:
                    st.info("プレイリストがありません。プレイリストタブで作成してください。")
            
            with tab_del:
                st.warning(f"⚠️ 選択した{len(selected_files)}曲をデータベースから削除します。（ファイル自体は削除されません）")
                col_del1, col_del2 = st.columns([1, 4])
                with col_del1:
                    if st.button("削除実行", type="primary", key="btn_delete_files"):
                        db.delete_audio_files(selected_files)
                        st.success(f"{len(selected_files)}曲を削除しました")
                        st.rerun()
        
        if has_sync_changes:
            st.info("同期設定に変更があります。「同期設定を保存」ボタンをクリックしてください。")
        
        # 個別編集セクション（詳細確認用）
        st.markdown("---")
        st.caption("※ リストのチェックボックスをクリックすると即座に保存されます。詳細は以下で確認できます。")
        
        # ファイル選択
        file_options = [f"{f['id']}: {f.get('title', 'Unknown')} - {f.get('artist', 'Unknown')}" for f in files]
        selected_idx = st.selectbox("詳細を確認するファイルを選択", range(len(files)), format_func=lambda x: file_options[x])
        
        if selected_idx is not None:
            selected_file = files[selected_idx]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**基本情報**")
                st.text_input("タイトル", value=selected_file.get('title', ''), key=f"title_{selected_file['id']}", disabled=True)
                st.text_input("アーティスト", value=selected_file.get('artist', ''), key=f"artist_{selected_file['id']}", disabled=True)
                st.text_input("アルバム", value=selected_file.get('album', ''), key=f"album_{selected_file['id']}", disabled=True)
                
                # Sync状態（ここも連動するが、リスト側で操作推奨）
                is_sync = bool(selected_file.get('sync'))
                st.toggle("同期対象", value=is_sync, disabled=True, key=f"toggle_{selected_file['id']}")
                st.caption("※ 上のリストで変更してください")
            
            with col2:
                st.write("**ファイル情報**")
                st.text_input("ファイル名", value=selected_file.get('filename', ''), disabled=True)
                st.text_input("コーデック", value=selected_file.get('codec', ''), disabled=True)
                st.text_input("ファイルパス", value=selected_file.get('filepath_from', ''), disabled=True)
                st.text_input("更新日時", value=selected_file.get('update_date', ''), disabled=True)
                
                # プレイリストに追加
                st.markdown("---")
                st.write("**プレイリストに追加**")
                playlists = db.get_all_playlists()
                if playlists:
                    playlist_names = [p['name'] for p in playlists]
                    selected_playlist = st.selectbox(
                        "追加先プレイリスト",
                        playlist_names,
                        key=f"playlist_select_{selected_file['id']}"
                    )
                    if st.button("➕ プレイリストに追加", key=f"add_to_playlist_{selected_file['id']}"):
                        playlist = next((p for p in playlists if p['name'] == selected_playlist), None)
                        if playlist:
                            db.add_to_playlist(playlist['id'], selected_file['id'])
                            st.success(f"「{selected_playlist}」に追加しました")
                else:
                    st.info("プレイリストがありません")
    
    else:
        st.info("音楽ファイルがありません。スキャンを実行してください。")


# ==================== タブ2: プレイリスト ====================
with tab2:
    st.header("プレイリスト管理")
    
    # プレイリスト一覧を取得
    playlists = db.get_all_playlists()
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("📋 プレイリスト一覧")
    
    with col2:
        # 新規プレイリスト作成
        with st.expander("＋ 新規作成"):
            new_playlist_name = st.text_input("プレイリスト名", key="new_playlist")
            if st.button("作成", key="create_playlist"):
                if new_playlist_name:
                    try:
                        db.create_playlist(new_playlist_name)
                        st.success(f"プレイリスト「{new_playlist_name}」を作成しました")
                        st.rerun()
                    except Exception as e:
                        st.error(f"作成に失敗: {e}")
                else:
                    st.warning("プレイリスト名を入力してください")
    
    # プレイリスト一覧を表示
    if playlists:
        # プレイリスト選択（ラジオボタンまたはセレクトボックス）
        selected_playlist_name = st.selectbox(
            "編集するプレイリストを選択",
            [p['name'] for p in playlists],
            key="playlist_selector"
        )
        
        # 選択されたプレイリストのIDを取得
        selected_playlist = next((p for p in playlists if p['name'] == selected_playlist_name), None)
        
        if selected_playlist:
            playlist_id = selected_playlist['id']
            items = db.get_playlist_items(playlist_id)
            
            st.markdown(f"### 🎵 {selected_playlist_name} ({len(items)}曲)")
            
            # プレイリスト操作エリア
            with st.expander("➕ 曲を追加する", expanded=False):
                # 簡易検索して追加
                search_add = st.text_input("追加する曲を検索", key="search_add_playlist")
                if search_add:
                    # 検索実行
                    all_files = db.get_all_audio_files()
                    hits = [
                        f for f in all_files
                        if search_add.lower() in (f.get('title') or '').lower() or
                           search_add.lower() in (f.get('artist') or '').lower()
                    ]
                    
                    if hits:
                        # 選択して追加
                        add_options = [f"{f['id']}: {f.get('title')} - {f.get('artist')}" for f in hits[:20]] # 最大20件
                        selected_add = st.selectbox("追加する曲を選択", add_options, key="select_add_playlist")
                        
                        if st.button("追加", key="btn_add_playlist"):
                            file_id = int(selected_add.split(':')[0])
                            db.add_to_playlist(playlist_id, file_id)
                            st.success("追加しました")
                            st.rerun()
                    else:
                        st.info("見つかりませんでした")
            
            # アイテムリスト表示と操作
            if items:
                # 編集モード
                edit_mode = st.checkbox("編集モード（削除・順序変更）", key="playlist_edit_mode")
                
                if edit_mode:
                    st.info("削除ボタンで削除、順序数値を変更してエンターで移動できます")
                    
                    # ヘッダー
                    h1, h2, h3, h4, h5 = st.columns([1, 4, 3, 3, 1])
                    h1.write("#")
                    h2.write("タイトル")
                    h3.write("アーティスト")
                    h4.write("アルバム")
                    h5.write("削除")
                    
                    for item in items:
                        c1, c2, c3, c4, c5 = st.columns([1, 4, 3, 3, 1])
                        
                        # 順序変更
                        current_pos = item.get('position', 0)
                        new_pos = c1.number_input(
                            "順序",
                            min_value=1,
                            max_value=len(items),
                            value=current_pos if current_pos > 0 else 1, # 0の場合は1にする
                            key=f"pos_{item['audio_file_id']}",
                            label_visibility="collapsed"
                        )
                        
                        if new_pos != current_pos:
                            db.update_playlist_item_position(playlist_id, item['audio_file_id'], new_pos)
                            st.rerun()
                            
                        c2.write(item.get('title', 'Unknown'))
                        c3.write(item.get('artist', 'Unknown'))
                        c4.write(item.get('album', 'Unknown'))
                        
                        # 削除ボタン
                        if c5.button("🗑️", key=f"del_{item['audio_file_id']}"):
                            db.remove_from_playlist(playlist_id, item['audio_file_id'])
                            st.rerun()
                            
                else:
                    # 通常表示（DataFrame）
                    item_df = pd.DataFrame(items)
                    display_cols = ['position', 'title', 'artist', 'album']
                    display_item_df = item_df[display_cols].copy()
                    display_item_df.columns = ['#', 'タイトル', 'アーティスト', 'アルバム']
                    st.dataframe(display_item_df, use_container_width=True, hide_index=True)
            else:
                st.info("このプレイリストには曲がありません")
                
    else:
        st.info("プレイリストがありません。新規作成してください。")


# ==================== タブ3: 設定 ====================
with tab3:
    st.header("設定")
    
    # 現在の設定を取得
    settings = db.get_all_settings()
    
    st.subheader("📁 ディレクトリ設定")
    
    # 対象ディレクトリ
    sync_dir_from = st.text_area(
        "対象ディレクトリ（1行に1つずつ）",
        value=settings.get('sync_dir_from', '').replace(',', '\n'),
        height=100,
        help="音楽ファイルをスキャンする対象ディレクトリ"
    )
    
    st.subheader("📄 ファイル設定")
    
    # 対象拡張子
    include_ext = st.text_input(
        "対象拡張子（カンマ区切り）",
        value=settings.get('include_ext', 'mp3,m4a,mp4'),
        help="スキャン対象とする音楽ファイルの拡張子"
    )
    
    st.subheader("🔄 同期設定")
    
    # 同期方法の選択
    sync_method = st.radio(
        "同期方法",
        ["FTP", "Rsync"],
        index=0 if settings.get('sync_method', 'ftp') == 'ftp' else 1,
        horizontal=True
    )
    
    if sync_method == "FTP":
        col1, col2 = st.columns(2)
        with col1:
            ftp_host = st.text_input("ホスト名/IPアドレス", value=settings.get('ftp_host', '192.168.10.3'))
            ftp_port = st.number_input("ポート番号", value=int(settings.get('ftp_port', 2221)), min_value=1, max_value=65535)
            ftp_dir = st.text_input("リモートディレクトリ", value=settings.get('ftp_dir', '/'))
        with col2:
            ftp_user = st.text_input("ユーザー名", value=settings.get('ftp_user', 'francis'))
            ftp_pass = st.text_input("パスワード", value=settings.get('ftp_pass', 'francis'), type="password")
            
    else: # Rsync
        col1, col2 = st.columns(2)
        with col1:
            rsync_host = st.text_input("ホスト名/IPアドレス", value=settings.get('rsync_host', ''))
            rsync_port = st.number_input("ポート番号", value=int(settings.get('rsync_port', 22)), min_value=1, max_value=65535)
            rsync_dir = st.text_input("リモートディレクトリ", value=settings.get('rsync_dir', ''))
        with col2:
            rsync_user = st.text_input("ユーザー名", value=settings.get('rsync_user', ''))
            rsync_opts = st.text_input("オプション", value=settings.get('rsync_opts', '-av --delete'))
            st.caption("※ パスワード認証はSSH鍵認証を推奨します")
    
    # 保存ボタン
    if st.button("💾 設定を保存", type="primary"):
        try:
            # 改行をカンマに変換
            db.set_setting('sync_dir_from', ','.join([d.strip() for d in sync_dir_from.split('\n') if d.strip()]))
            db.set_setting('include_ext', include_ext)
            
            # 同期設定の保存
            db.set_setting('sync_method', sync_method.lower())
            if sync_method == "FTP":
                db.set_setting('ftp_host', ftp_host)
                db.set_setting('ftp_port', str(ftp_port))
                db.set_setting('ftp_dir', ftp_dir)
                db.set_setting('ftp_user', ftp_user)
                db.set_setting('ftp_pass', ftp_pass)
            else:
                db.set_setting('rsync_host', rsync_host)
                db.set_setting('rsync_port', str(rsync_port))
                db.set_setting('rsync_dir', rsync_dir)
                db.set_setting('rsync_user', rsync_user)
                db.set_setting('rsync_opts', rsync_opts)
            
            st.success("✅ 設定を保存しました")
            logger.info("Settings updated")
        except Exception as e:
            st.error(f"❌ 設定の保存に失敗: {e}")
            logger.error(f"Failed to save settings: {e}")
    
    # データベース情報
    st.markdown("---")
    st.subheader("🗄️ データベース情報")
    st.text_input("データベースパス", value=db.db_path, disabled=True)
    
    # Excel移行
    st.markdown("---")
    st.subheader("📊 Excelからの移行")
    st.info("既存のAudioSyncData.xlsxからデータを移行できます")
    
    if st.button("📥 Excelデータを移行", type="secondary"):
        st.warning("この機能は`migrate_from_excel.py`スクリプトを実行してください")
        st.code("python src/audiosync/migrate_from_excel.py", language="bash")


# ==================== フッター ====================
st.markdown("---")
st.caption("AudioSync Web版 | Powered by Streamlit")
