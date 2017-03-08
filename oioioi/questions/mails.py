from django.core.mail import EmailMessage
from django.core.urlresolvers import reverse
from django.dispatch import receiver, Signal
from django.template.loader import render_to_string

from oioioi.questions.models import MessageNotifierConfig, QuestionSubscription

new_question_signal = Signal(providing_args=['request', 'instance'])
new_reply_signal = Signal(providing_args=['request', 'instance'])


#------------------------ Receivers ----------------------------#

@receiver(new_reply_signal)
def notify_new_reply(sender, request, instance, **kwargs):
    send_mail_new_reply(request, instance)


@receiver(new_question_signal)
def notify_about_new_question(sender, request, instance, **kwargs):
    conf = MessageNotifierConfig.objects.filter(contest=instance.contest)
    users_to_notify = [x.user for x in conf]
    for u in users_to_notify:
        send_email_about_new_question(u, request, instance)


#---------------------- Mail senders ---------------------------#

def send_mail_new_reply(request, instance):
    msg_link = request.build_absolute_uri(reverse(
        'message',
        kwargs={
            'contest_id': instance.contest,
            'message_id': instance.top_reference.id
        }
    ))
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


def send_email_about_new_question(recipient, request, msg_obj):
    context = {'recipient': recipient, 'msg': msg_obj,
               'msg_link': request.build_absolute_uri(
                   reverse('message',
                           kwargs={
                               'contest_id': request.contest.id,
                               'message_id': msg_obj.id
                           })
               )}

    subject = render_to_string('questions/new_msg_mail_subject.txt', context)

    subject = ' '.join(subject.strip().splitlines())
    body = render_to_string('questions/new_msg_mail_body.txt', context)

    email = EmailMessage(subject=subject, body=body, to=[recipient.email])
    email.send(fail_silently=True)
