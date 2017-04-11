import time

from django.core.management.base import BaseCommand
from django.utils.translation import ugettext as _
from django.conf import settings
from oioioi.questions.models import Message, QuestionSubscription

def mailnotify(instance):
    msg_link = reverse(
        'message',
        kwargs={
            'contest_id': instance.contest,
            'message_id': instance.top_reference.id
        }
    )
    print msg_link
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
            email.send(fail_silently=True)
    else:  # PRIVATE
        author = instance.top_reference.author
        subscriptions = subscriptions.filter(user=author)
        if subscriptions and author.email:
            email = EmailMessage(subject=subject, body=body, to=[author.email])
            email.send(fail_silently=True)


class Command(BaseCommand):
    help = _(
        "mailnotifyd" # TODO
    )

    def handle(self, *args, **options):
        while True:
            #messages = Message.objects.filter(mail_sent=False)
            # TODO filter by pub date, etc.
            #for msg in messages:
            #    mailnotify(msg)
            print full_url
            time.sleep(settings.MAILNOTIFYD_INTERVAL)
