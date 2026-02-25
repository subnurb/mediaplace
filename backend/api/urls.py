from django.urls import path
from . import views, sync_views, library_views

urlpatterns = [
    # App authentication
    path("auth/register/", views.app_register),
    path("auth/login/", views.app_login),
    path("auth/logout/", views.app_logout),
    path("auth/me/", views.me),
    path("auth/profile/", views.update_profile),
    path("auth/change-password/", views.change_password),

    # YouTube OAuth — callback URL unchanged so Google Cloud Console config stays valid
    path("auth/youtube-connect/", views.youtube_connect),
    path("auth/callback/", views.youtube_callback),

    # SoundCloud OAuth
    path("auth/soundcloud-connect/", views.soundcloud_connect),
    path("auth/soundcloud/callback/", views.soundcloud_callback),

    # Google sign-in
    path("auth/google/", views.google_login),
    path("auth/google/callback/", views.google_callback),

    # Sources
    path("sources/", views.sources_list),
    path("sources/<int:source_id>/", views.source_detail),
    path("sources/<int:source_id>/playlists/", sync_views.source_playlists),

    # Jobs (MP3 → YouTube tool)
    path("jobs/file/", views.job_upload_file),
    path("jobs/url/", views.job_upload_url),
    path("jobs/download/", views.job_download),
    path("jobs/publish/", views.job_publish),

    # Sync (playlist sync tool)
    path("sync/", sync_views.sync_list_create),
    path("sync/log/", sync_views.sync_log_view),
    path("sync/<int:job_id>/", sync_views.sync_detail),
    path("sync/<int:job_id>/push/", sync_views.sync_push),
    path("sync/<int:job_id>/export/", sync_views.sync_export),
    path("sync/<int:job_id>/analyze/", sync_views.sync_analyze),
    path("sync/<int:job_id>/tracks/<int:track_id>/upload/", sync_views.sync_upload_track),
    path("sync/<int:job_id>/tracks/<int:track_id>/skip/", sync_views.sync_skip_track),
    path("sync/<int:job_id>/confirm-all/", sync_views.sync_confirm_all),
    path("sync/<int:job_id>/tracks/<int:track_id>/confirm/", sync_views.sync_confirm_track),
    path("sync/<int:job_id>/tracks/<int:track_id>/unconfirm/", sync_views.sync_unconfirm_track),
    path("sync/<int:job_id>/tracks/<int:track_id>/reject/", sync_views.sync_reject_track),
    path("sync/<int:job_id>/tracks/<int:track_id>/select/", sync_views.sync_select_match),
    path("sync/<int:job_id>/tracks/<int:track_id>/resolve-url/", sync_views.sync_resolve_url),

    # Library (cross-platform music library)
    path("library/", library_views.library_list),
    path("library/tracks/<int:ts_id>/fingerprint/", library_views.library_fingerprint_track),
    path("library/settings/", library_views.library_settings),
    path("library/settings/<int:playlist_id>/", library_views.library_settings_detail),
    path("library/settings/<int:playlist_id>/sync/", library_views.library_settings_sync),
    path("library/settings/<int:playlist_id>/stop/", library_views.library_settings_stop),
    path("library/analyze-all/", library_views.library_analyze_all),
]
