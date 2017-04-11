import json

from django.core import mail
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from django.test import RequestFactory

from oioioi.base.tests import TestCase, check_not_accessible, fake_time
from oioioi.contests.models import Contest, ProblemInstance
from oioioi.programs.controllers import ProgrammingContestController
from oioioi.questions.models import Message, ReplyTemplate
from oioioi.base.notification import NotificationHandler
from .views import visible_messages
from oioioi.questions.management.commands.mailnotifyd import mailnotify

from datetime import datetime


class TestContestControllerMixin(object):
    def users_to_receive_public_message_notification(self):
        return self.registration_controller().filter_participants(User
                .objects.all())

ProgrammingContestController.mix_in(TestContestControllerMixin)


class TestQuestions(TestCase):
    fixtures = ['test_users', 'test_contest', 'test_full_package',
                'test_problem_instance', 'test_messages', 'test_templates',
                'test_subscriptions']

    def test_visibility(self):
        contest = Contest.objects.get()
        all_messages = ['problem-question', 'contest-question',
                'public-answer', 'private-answer']
        url = reverse('contest_messages', kwargs={'contest_id': contest.id})

        def check_visibility(*should_be_visible):
            response = self.client.get(url)
            for m in all_messages:
                if m in should_be_visible:
                    self.assertIn(m, response.content)
                else:
                    self.assertNotIn(m, response.content)
        self.client.login(username='test_user')
        check_visibility('public-answer', 'private-answer')
        self.client.login(username='test_user2')
        check_visibility('public-answer')
        self.client.login(username='test_admin')
        check_visibility('public-answer', 'private-answer')

    def test_pub_date(self):
        contest = Contest.objects.get()
        all_messages = ['question-visible', 'question-hidden1',
                'question-hidden2', 'response-hidden',
                'visible-response-to-hidden']
        url = reverse('contest_messages', kwargs={'contest_id': contest.id})
        timestamp = datetime(2013, 9, 7, 13, 40, 0, tzinfo=timezone.utc)

        def check_visibility(*should_be_visible):
            with fake_time(timestamp):
                response = self.client.get(url)
            for m in all_messages:
                if m in should_be_visible:
                    self.assertIn(m, response.content)
                else:
                    self.assertNotIn(m, response.content)

        self.client.login(username='test_user')
        check_visibility('question-visible')
        self.client.login(username='test_admin')
        check_visibility('response-hidden', 'question-hidden1',
                'visible-response-to-hidden')

    def test_user_date(self):
        ta = datetime(1970, 1, 1, 12, 30, tzinfo=timezone.utc)
        tb = datetime(1970, 1, 1, 13, 30, tzinfo=timezone.utc)
        self.assertEquals(Message(date=ta, pub_date=None).get_user_date(), ta)
        self.assertEquals(Message(date=ta, pub_date=tb).get_user_date(), tb)

    def test_visible_messages(self):
        contest = Contest.objects.get()
        timestamp = datetime(2013, 9, 7, 13, 40, 0, tzinfo=timezone.utc)

        def make_request(username):
            request = RequestFactory().request()
            request.timestamp = timestamp
            request.contest = contest
            request.user = User.objects.get(username=username)
            return request

        self.assertListEqual([5, 4, 3, 2, 1],
                [m.id for m in visible_messages(make_request('test_user'))])
        self.assertListEqual([5, 4],
                [m.id for m in visible_messages(make_request('test_user2'))])
        self.assertListEqual(range(9, 0, -1),
                [m.id for m in visible_messages(make_request('test_admin'))])

    def test_new_labels(self):
        self.client.login(username='test_user')
        contest = Contest.objects.get()
        list_url = reverse('contest_messages',
                kwargs={'contest_id': contest.id})
        timestamp = timezone.make_aware(datetime.utcfromtimestamp(1347025200))
        with fake_time(timestamp):
            response = self.client.get(list_url)
        self.assertEqual(response.content.count('>NEW<'), 2)
        public_answer = Message.objects.get(topic='public-answer')
        with fake_time(timestamp):
            response = self.client.get(reverse('message', kwargs={
                'contest_id': contest.id, 'message_id': public_answer.id}))
        self.assertIn('public-answer-body', response.content)
        self.assertNotIn('contest-question', response.content)
        self.assertNotIn('problem-question', response.content)
        with fake_time(timestamp):
            response = self.client.get(list_url)
        self.assertEqual(response.content.count('>NEW<'), 1)

    def test_ask_and_reply(self):
        self.client.login(username='test_user2')
        contest = Contest.objects.get()
        pi = ProblemInstance.objects.get()
        url = reverse('add_contest_message', kwargs={'contest_id': contest.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        form = response.context['form']
        self.assertEqual(len(form.fields['category'].choices) - 1, 2)

        post_data = {
                'category': 'p_%d' % (pi.id,),
                'topic': 'the-new-question',
                'content': 'the-new-body',
            }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        new_question = Message.objects.get(topic='the-new-question')
        self.assertEqual(new_question.content, 'the-new-body')
        self.assertEqual(new_question.kind, 'QUESTION')
        self.assertIsNone(new_question.top_reference)
        self.assertEqual(new_question.contest, contest)
        self.assertEqual(new_question.problem_instance, pi)
        self.assertEqual(new_question.author.username, 'test_user2')

        self.client.login(username='test_admin')
        list_url = reverse('contest_messages',
                kwargs={'contest_id': contest.id})
        response = self.client.get(list_url)
        self.assertIn('the-new-question', response.content)

        url = reverse('message', kwargs={'contest_id': contest.id,
            'message_id': new_question.id})
        response = self.client.get(url)
        self.assertIn('form', response.context)

        post_data = {
                'kind': 'PUBLIC',
                'topic': 're-new-question',
                'content': 're-new-body',
                'save_template': True,
            }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        post_data = {
                'kind': 'PUBLIC',
                'topic': 'another-re-new-question',
                'content': 'another-re-new-body',
                'save_template': False,
            }
        response = self.client.post(url, post_data)
        self.assertRaises(ReplyTemplate.DoesNotExist,
                          lambda: ReplyTemplate.objects
                                  .get(content='another-re-new-body'))
        self.assertEqual(response.status_code, 302)
        new_reply = Message.objects.get(topic='re-new-question')
        self.assertEqual(new_reply.content, 're-new-body')
        self.assertEqual(new_reply.kind, 'PUBLIC')
        self.assertEqual(new_reply.top_reference, new_question)
        self.assertEqual(new_reply.contest, contest)
        self.assertEqual(new_reply.problem_instance, pi)
        self.assertEqual(new_reply.author.username, 'test_admin')

        self.client.login(username='test_user')
        q_url = reverse('message', kwargs={'contest_id': contest.id,
            'message_id': new_question.id})
        check_not_accessible(self, q_url)
        repl_url = reverse('message', kwargs={'contest_id': contest.id,
            'message_id': new_reply.id})
        response = self.client.get(repl_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('re-new-question', response.content)
        self.assertIn('re-new-body', response.content)
        self.assertNotIn('the-new-question', response.content)
        self.assertNotIn('the-new-body', response.content)
        response = self.client.get(list_url)
        self.assertIn(repl_url.encode('utf-8'), response.content)
        self.assertIn('re-new-question', response.content)
        self.assertNotIn('the-new-question', response.content)

        self.client.login(username='test_user2')
        response = self.client.get(q_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('the-new-question', response.content)
        self.assertIn('the-new-body', response.content)
        self.assertIn('re-new-body', response.content)
        response = self.client.get(list_url)
        self.assertIn(q_url.encode('utf-8'), response.content)
        self.assertIn('re-new-question', response.content)
        self.assertNotIn('the-new-question', response.content)

    def test_reply_notification(self):
        flags = {}
        flags['user_1001_got_notification'] = False
        flags['user_1002_got_notification'] = False

        @classmethod
        def fake_send_notification(cls, user, notification_type,
                    notification_message, notificaion_message_arguments):
            if user.pk == 1002:
                flags['user_1002_got_notification'] = True
            if user.pk == 1001:
                flags['user_1001_got_notification'] = True

        send_notification_backup = NotificationHandler.send_notification
        NotificationHandler.send_notification = fake_send_notification

        # Test user asks a new question
        self.client.login(username='test_user2')
        contest = Contest.objects.get()
        pi = ProblemInstance.objects.get()
        url = reverse('add_contest_message', kwargs={'contest_id': contest.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        post_data = {
                'category': 'p_%d' % (pi.id,),
                'topic': 'the-new-question',
                'content': 'the-new-body',
            }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        new_question = Message.objects.get(topic='the-new-question')

        # Test admin replies his question
        self.client.login(username='test_admin')
        list_url = reverse('contest_messages',
                kwargs={'contest_id': contest.id})
        response = self.client.get(list_url)
        self.assertIn('the-new-question', response.content)

        url = reverse('message', kwargs={'contest_id': contest.id,
            'message_id': new_question.id})
        response = self.client.get(url)
        self.assertIn('form', response.context)

        post_data = {
                'kind': 'PRIVATE',
                'topic': 're-new-question',
                'content': 're-new-body',
                'save_template': True,
            }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)

        # Check if a notification for user was send
        self.assertTrue(flags['user_1002_got_notification'])
        self.assertFalse(flags['user_1001_got_notification'])

        NotificationHandler.send_notification = send_notification_backup

    def test_public_message_notification(self):
        flags = {}
        flags['user_1001_got_notification'] = False
        flags['user_1002_got_notification'] = False

        @classmethod
        def fake_send_notification(cls, user, notification_type,
                    notification_message, notificaion_message_arguments):
            if user.pk == 1002:
                flags['user_1002_got_notification'] = True
            if user.pk == 1001:
                flags['user_1001_got_notification'] = True

        send_notification_backup = NotificationHandler.send_notification
        NotificationHandler.send_notification = fake_send_notification

        # Test user asks a new question
        self.client.login(username='test_user2')
        contest = Contest.objects.get()
        pi = ProblemInstance.objects.get()

        url = reverse('add_contest_message', kwargs={'contest_id': contest.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        post_data = {
                'category': 'p_%d' % (pi.id,),
                'topic': 'the-new-question',
                'content': 'the-new-body',
            }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        new_question = Message.objects.get(topic='the-new-question')

        # Test admin replies his question
        self.client.login(username='test_admin')
        list_url = reverse('contest_messages',
                kwargs={'contest_id': contest.id})
        response = self.client.get(list_url)
        self.assertIn('the-new-question', response.content)

        url = reverse('message', kwargs={'contest_id': contest.id,
            'message_id': new_question.id})
        response = self.client.get(url)
        self.assertIn('form', response.context)

        post_data = {
                'kind': 'PUBLIC',
                'topic': 're-new-question',
                'content': 're-new-body',
                'save_template': True,
            }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)

        self.assertTrue(flags['user_1002_got_notification'])
        self.assertTrue(flags['user_1001_got_notification'])

        NotificationHandler.send_notification = send_notification_backup

    def test_filtering(self):
        self.client.login(username='test_admin')
        contest = Contest.objects.get()
        url = reverse('contest_messages', kwargs={'contest_id': contest.id})

        get_data = {'author': 'test_admin'}
        response = self.client.get(url, get_data)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('general-question', response.content)
        self.assertNotIn('problem-question', response.content)
        self.assertIn('public-answer', response.content)
        self.assertIn('private-answer', response.content)

        get_data['author'] = 'test_user'
        response = self.client.get(url, get_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('general-question', response.content)
        self.assertIn('problem-question', response.content)
        self.assertNotIn('public-answer', response.content)
        self.assertNotIn('private-answer', response.content)

        get_data['category'] = 'r_1'
        response = self.client.get(url, get_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('general-question', response.content)
        self.assertNotIn('problem-question', response.content)
        self.assertNotIn('public-answer', response.content)
        self.assertNotIn('private-answer', response.content)

        get_data['category'] = 'p_1'
        response = self.client.get(url, get_data)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('general-question', response.content)
        self.assertIn('problem-question', response.content)
        self.assertNotIn('public-answer', response.content)
        self.assertNotIn('private-answer', response.content)

        self.client.login(username='test_user')
        response = self.client.get(url, get_data)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('general-question', response.content)
        self.assertNotIn('problem-question', response.content)
        self.assertNotIn('public-answer', response.content)
        self.assertIn('private-answer', response.content)

    def test_authors_list(self):
        self.client.login(username='test_admin')
        contest = Contest.objects.get()
        url = reverse('get_messages_authors',
                      kwargs={'contest_id': contest.id})
        response = self.client.get(url, {'substr': ''})
        self.assertEquals(404, response.status_code)
        response = self.client.get(url)
        self.assertEquals(404, response.status_code)

        response = self.client.get(url, {'substr': 'te'})
        self.assertEquals(200, response.status_code)
        response = json.loads(response.content)
        self.assertListEqual(['test_admin (Test Admin)',
                              'test_user (Test User)'], response)

        response = self.client.get(url, {'substr': 'test admin'})
        response = json.loads(response.content)
        self.assertListEqual(['test_admin (Test Admin)'], response)

        self.client.login(username='test_user')
        check_not_accessible(self, url)

    def test_change_category(self):
        pi = ProblemInstance.objects.get()
        r = pi.round
        q = Message.objects.get(topic="problem-question")
        a1, a2 = Message.objects.filter(top_reference=q)
        self.client.get('/c/c/')  # 'c' becomes the current contest

        def change_category(msg, cat):
            url = reverse('oioioiadmin:questions_message_change',
                          args=(msg.id,))
            self.client.login(username='test_admin')
            response = self.client.get(url)
            self.assertIn('form', response.context)

            post_data = {
                'kind': msg.kind,
                'category': cat,
                'topic': msg.topic,
                'content': msg.content,
            }
            response = self.client.post(url, post_data)
            self.assertEqual(response.status_code, 302)

        # Change a1 to round question
        change_category(a1, 'r_%d' % r.id)
        q = Message.objects.get(topic="problem-question")
        a1, a2 = Message.objects.filter(top_reference=q)
        self.assertEqual(a1.round, r)
        self.assertEqual(a2.round, r)
        self.assertEqual(q.round, r)
        self.assertTrue(a1.problem_instance is None)
        self.assertTrue(a2.problem_instance is None)
        self.assertTrue(q.problem_instance is None)
        # Change q to problem question
        change_category(q, 'p_%d' % pi.id)
        q = Message.objects.get(topic="problem-question")
        a1, a2 = Message.objects.filter(top_reference=q)
        self.assertEqual(a1.problem_instance, pi)
        self.assertEqual(a2.problem_instance, pi)
        self.assertEqual(q.problem_instance, pi)
        self.assertEqual(a1.round, pi.round)
        self.assertEqual(a2.round, pi.round)
        self.assertEqual(q.round, pi.round)

    def test_change_denied(self):
        self.client.login(username='test_user')
        self.client.get('/c/c/')  # 'c' becomes the current contest

        msg = Message.objects.filter(author__username='test_admin')[0]
        url = reverse('oioioiadmin:questions_message_change',
                      args=(msg.id,))
        check_not_accessible(self, url)

    def test_reply_templates(self):
        contest = Contest.objects.get()
        self.client.login(username='test_admin')
        url1 = reverse('get_reply_templates',
                       kwargs={'contest_id': contest.id})
        response = self.client.get(url1)
        templates = json.loads(response.content)
        self.assertEqual(templates[0]['name'], "N/A")
        self.assertEqual(templates[0]['content'], "No answer.")
        self.assertEqual(templates[3]['name'], "What contest is this?")
        self.assertEqual(len(templates), 4)
        url_inc = reverse('increment_template_usage',
                          kwargs={'contest_id': contest.id, 'template_id': 4})
        for _i in xrange(12):
            response = self.client.get(url_inc)
        response = self.client.get(url1)
        templates = json.loads(response.content)
        self.assertEqual(templates[0]['name'], "What contest is this?")
        self.assertEqual(len(templates), 4)
        self.client.login(username='test_user')
        check_not_accessible(self, url1)

    def test_check_new_messages(self):
        self.client.login(username='test_user')
        url = reverse('check_new_messages',
                kwargs={'contest_id': 'c', 'topic_id': 2})
        resp = self.client.get(url, {'timestamp': 1347000000})
        data = json.loads(resp.content)['messages']

        self.assertEqual(data[1][0], u'private-answer')

    def test_mail_notifications(self):
        # Notify about a private message
        message = Message.objects.get(pk=3)
        mailnotify(message)
        m = mail.outbox[0]
        self.assertEquals(len(mail.outbox), 1)
        self.assertIn("New public question", m.subject)
        self.assertEquals("test_user2@example.com", m.to[0])
        self.assertIn("public question in category has just been rev", m.body)
        self.assertIn("re-new-body", m.body)
        # Do not notify about a question
        question = Message.objects.get(pk=2)
        mailnotify(question)
        self.assertEquals(len(mail.outbox), 1)


class TestUserInfo(TestCase):
    fixtures = ['test_users', 'test_contest', 'test_full_package',
                'test_problem_instance', 'test_messages', 'test_templates']

    def test_user_info_page(self):
        contest = Contest.objects.get()
        user = User.objects.get(pk=1001)
        url = reverse('user_info', kwargs={'contest_id': contest.id,
                                           'user_id': user.id})

        self.client.login(username='test_admin')
        response = self.client.get(url)
        self.assertIn('User info', response.content)
        self.assertIn("User's messages", response.content)
        self.assertIn('general-question', response.content)
