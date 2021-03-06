from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.db import models
from django.utils.translation import ugettext_lazy as _
from oioioi.base.utils.validators import validate_whitespaces
from oioioi.contests.models import Submission, Contest


class Disqualification(models.Model):
    contest = models.ForeignKey(Contest, verbose_name=_("contest"))
    user = models.ForeignKey(User, verbose_name=_("user"))
    # Leave submission empty to make contest-wide disqualification
    submission = models.ForeignKey(Submission, null=True, blank=True,
            verbose_name=_("submission"))
    title = models.CharField(max_length=255,
            validators=[MaxLengthValidator(255), validate_whitespaces],
            verbose_name=_("title"))
    content = models.TextField(verbose_name=_("content"))
    guilty = models.BooleanField(default=True)

    class Meta(object):
        verbose_name = _("disqualification")
        verbose_name_plural = _("disqualifications")

    def clean(self):
        if self.submission and self.submission.user != self.user:
            raise ValidationError(_("The submision does not match the user."))

    def save(self, *args, **kwargs):
        if self.submission:
            assert self.contest.id == \
                   self.submission.problem_instance.contest_id
            assert self.user.id == self.submission.user_id

        super(Disqualification, self).save(*args, **kwargs)
