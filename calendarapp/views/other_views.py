from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect
from django.views import generic
from django.utils.safestring import mark_safe
from datetime import timedelta, datetime, date
import calendar
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from calendarapp.models import EventMember, Event 
from calendarapp.utils import Calendar
from calendarapp.forms import EventForm, AddMemberForm
from django.views.generic import View
from django.contrib.auth.models import User
from main_app.models import Manager, CustomUser, ProjectEngineer


def get_date(req_day):
    if req_day:
        year, month = (int(x) for x in req_day.split("-"))
        return date(year, month, day=1)
    return datetime.today()


def prev_month(d):
    first = d.replace(day=1)
    prev_month = first - timedelta(days=1)
    month = "month=" + str(prev_month.year) + "-" + str(prev_month.month)
    return month


def next_month(d):
    days_in_month = calendar.monthrange(d.year, d.month)[1]
    last = d.replace(day=days_in_month)
    next_month = last + timedelta(days=1)
    month = "month=" + str(next_month.year) + "-" + str(next_month.month)
    return month

class DashboardView(View):
    template_name = "calendar/calendarapp/dashboard.html"

    def get(self, request, *args, **kwargs):
        events = Event.objects.get_all_events(user=request.user) # type: ignore
        running_events = Event.objects.get_running_events(user=request.user) # type: ignore
        latest_events = Event.objects.filter(user=request.user).order_by("-id")[:10]
        context = {
            "total_event": events.count(),
            "running_events": running_events,
            "latest_events": latest_events,
        }
        return render(request, self.template_name, context)


class CalendarView(generic.ListView):
    model = Event
    template_name = "calendar/calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        d = get_date(self.request.GET.get("month", None))
        cal = Calendar(d.year, d.month)
        html_cal = cal.formatmonth(withyear=True)
        context["calendar"] = mark_safe(html_cal)
        context["prev_month"] = prev_month(d)
        context["next_month"] = next_month(d)
        return context


def create_event(request, manager_id=-1, projectEngineer_id=-1):
    form = EventForm(request.POST or None)

    if manager_id!=-1:
        manager = get_object_or_404(Manager, id=manager_id)
        userC = CustomUser.objects.get(id=manager.admin.id) # type: ignore
    elif projectEngineer_id!=-1:
        projectEngineer = get_object_or_404(ProjectEngineer, id=projectEngineer_id)
        userC = CustomUser.objects.get(id=projectEngineer.admin.id) # type: ignore
    else:
        userC = request.user
    
    referer = request.META.get('HTTP_REFERER')

    if request.POST and form.is_valid():
        title = form.cleaned_data["title"]
        description = form.cleaned_data["description"]
        start_time = form.cleaned_data["start_time"]
        end_time = form.cleaned_data["end_time"]
        Event.objects.get_or_create(
            user=userC,
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
        )
        # return HttpResponseRedirect(reverse("calendar/calendarapp/calendar"))
        return HttpResponseRedirect(referer)
    return render(request, "calendar/event.html", {"form": form})


class EventEdit(generic.UpdateView):
    model = Event
    fields = ["title", "description", "start_time", "end_time"]
    template_name = "calendar/event.html"


def event_details(request, event_id):
    event = Event.objects.get(id=event_id)
    eventmember = EventMember.objects.filter(event=event)
    context = {"event": event, "eventmember": eventmember}
    return render(request, "calendar/event-details.html", context)


def add_eventmember(request, event_id):
    forms = AddMemberForm()
    if request.method == "POST":
        forms = AddMemberForm(request.POST)
        if forms.is_valid():
            member = EventMember.objects.filter(event=event_id)
            event = Event.objects.get(id=event_id)
            if member.count() <= 9:
                user = forms.cleaned_data["user"]
                EventMember.objects.create(event=event, user=user)
                return redirect("calendar/calendarapp/calendar")
            else:
                print("--------------User limit exceed!-----------------")
    context = {"form": forms}
    return render(request, "calendar/add_member.html", context)


class EventMemberDeleteView(generic.DeleteView):
    model = EventMember
    template_name = "calendar/event_delete.html"
    success_url = reverse_lazy("calendar/calendarapp/calendar")

class CalendarViewNew(generic.View):
    template_name = "calendar/calendarapp/calendar.html"
    form_class = EventForm

    def get(self, request, manager_id=-1, projectEngineer_id=-1, *args, **kwargs):
        forms = self.form_class()

        if manager_id!=-1:
            manager = get_object_or_404(Manager, id=manager_id)
            userC = CustomUser.objects.get(id=manager.admin.id) # type: ignore
        elif projectEngineer_id!=-1:
            projectEngineer = get_object_or_404(ProjectEngineer, id=projectEngineer_id)
            userC = CustomUser.objects.get(id=projectEngineer.admin.id) # type: ignore
        else:
            userC = request.user


        events = Event.objects.get_all_events(user=userC) # type: ignore
        events_month = Event.objects.get_running_events(user=userC) # type: ignore
        event_list = []
        # start: '2020-09-16T16:00:00'
        for event in events:
            event_list.append(
                {   "id": event.id,
                    "title": event.title,
                    "start": event.start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "end": event.end_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "description": event.description,
                }
            )
        
        context = {"form": forms, "events": event_list,
                   "events_month": events_month, "name": userC}
        return render(request, self.template_name, context)

    def post(self, request, manager_id=-1, projectEngineer_id=-1, *args, **kwargs):
        forms = self.form_class(request.POST)
        referer = request.META.get('HTTP_REFERER')

        if manager_id!=-1:
            manager = get_object_or_404(Manager, id=manager_id)
            userC = CustomUser.objects.get(id=manager.admin.id) # type: ignore
        elif projectEngineer_id!=-1:
            projectEngineer = get_object_or_404(ProjectEngineer, id=projectEngineer_id)
            userC = CustomUser.objects.get(id=projectEngineer.admin.id) # type: ignore
        else:
            userC = request.user

        if forms.is_valid():
            form = forms.save(commit=False)
            form.user = userC
            form.save()
            # return redirect("/calendar")
            return HttpResponseRedirect(referer)
        context = {"form": forms}
        return render(request, self.template_name, context)


@csrf_exempt
def delete_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        event.delete()
        return JsonResponse({'message': 'Event sucess delete.'})
    else:
        return JsonResponse({'message': 'Error!'}, status=400)

@csrf_exempt
def next_week(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        next = event
        next.id = None # type: ignore
        next.start_time += timedelta(days=7)
        next.end_time += timedelta(days=7)
        next.save()
        return JsonResponse({'message': 'Sucess!'})
    else:
        return JsonResponse({'message': 'Error!'}, status=400)

@csrf_exempt
def next_day(request, event_id):

    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        next = event
        next.id = None # type: ignore
        next.start_time += timedelta(days=1)
        next.end_time += timedelta(days=1)
        next.save()
        return JsonResponse({'message': 'Sucess!'})
    else:
        return JsonResponse({'message': 'Error!'}, status=400)
