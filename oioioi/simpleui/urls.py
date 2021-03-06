from django.conf.urls import patterns, url

noncontest_patterns = patterns('oioioi.simpleui.views',
    url(r'^teacher-dashboard/$', 'teacher_dashboard_view',
        name='teacher_dashboard')
)

contest_patterns = patterns('oioioi.simpleui.views',
    url(r'^contest-dashboard/$', 'contest_dashboard_view',
        name='teacher_contest_dashboard'),
    url(r'^contest-dashboard/(?P<round_pk>[0-9]+)/$',
        'contest_dashboard_view', name='teacher_contest_dashboard'),
    url(r'^problem-settings/(?P<problem_instance_id>\d+)/$',
        'problem_settings', name='problem_settings'),
)
