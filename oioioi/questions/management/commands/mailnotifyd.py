import time
from datetime import datetime

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from oioioi.questions.models import Message, QuestionSubscription


def mailnotify(instance):
    m_id = instance.top_reference.id if instance.top_reference else instance.id
    msg_link = reverse(
        'message',
        kwargs={
            'contest_id': instance.contest,
            'message_id': m_id
        }
    )

    msg_link = settings.DISPLAYED_ROOT_URL + msg_link
    context = {'msg': instance, 'msg_link': msg_link}

    subject = render_to_string(
        'questions/reply_notification_subject.txt',
        context
    )
    subject = ' '.join(subject.strip().splitlines())
    body = render_to_string(
        'questions/reply_notification_body.txt',
        context
    )

    subscriptions = QuestionSubscription.objects \
        .filter(contest=instance.contest)

    if instance.kind == 'PUBLIC':
        # There may be users without an e-mail, filter them out
        mails = [sub.user.email for sub in subscriptions if sub.user.email]

        # if there are any users with e-mails
        if mails:
            email = EmailMessage(subject=subject, body=body, bcc=mails)
            print "Sending a public mail"
            print email
            email.send(fail_silently=True)
    else:  # PRIVATE
        author = instance.top_reference.author
        subscriptions = subscriptions.filter(user=author)
        if subscriptions and author.email:
            email = EmailMessage(subject=subject, body=body, to=[author.email])
            print "Sending a private mail"
            print email
            email.send(fail_silently=True)

    instance.mail_sent = True
    instance.save()

class Command(BaseCommand):
    help = _(
        """
        Periodically scans the whole database for messages with unsent
        notifications.
        We can't do this easily without a daemon since we have to support
        delayed publishing of news
        """
    )

    def handle(self, *args, **options):
        while True:
            messages = Message.objects.filter(
                mail_sent=False,
                pub_date__lte=datetime.now()
            )
            for msg in messages:
                mailnotify(msg)
            time.sleep(settings.MAILNOTIFYD_INTERVAL)
