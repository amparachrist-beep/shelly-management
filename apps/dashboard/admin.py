from django.contrib import admin
from django.utils.html import format_html
from .models import (
    DashboardWidget, UserDashboardLayout, DashboardNotification,
    DashboardQuickAction, CachedDashboardData, UserWidgetPreference,
    DashboardAnalytics
)


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ['name', 'widget_type_display', 'enabled_by_default', 'order', 'created_at']
    list_filter = ['widget_type', 'enabled_by_default', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['enabled_by_default', 'order']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = []

    fieldsets = (
        ('Informations Générales', {
            'fields': ('name', 'widget_type', 'description', 'icon')
        }),
        ('Configuration', {
            'fields': ('config', 'default_position', 'default_size')
        }),
        ('Permissions', {
            'fields': ('allowed_roles', 'requires_permission')
        }),
        ('Visibilité', {
            'fields': ('enabled_by_default', 'order')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def widget_type_display(self, obj):
        return obj.get_widget_type_display()

    widget_type_display.short_description = 'Type'

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('order', 'name')


@admin.register(UserDashboardLayout)
class UserDashboardLayoutAdmin(admin.ModelAdmin):
    list_display = ['user_display', 'theme_display', 'density_display', 'last_accessed']
    list_filter = ['theme', 'density', 'auto_refresh']
    search_fields = ['user__email', 'user__username']
    readonly_fields = ['created_at', 'updated_at', 'last_accessed']

    fieldsets = (
        ('Utilisateur', {
            'fields': ('user',)
        }),
        ('Configuration', {
            'fields': ('theme', 'density', 'auto_refresh', 'refresh_interval', 'default_view')
        }),
        ('Layout', {
            'fields': ('layout_config',),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('last_accessed', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def user_display(self, obj):
        return obj.user.email if obj.user else '-'

    user_display.short_description = 'Utilisateur'

    def theme_display(self, obj):
        return obj.get_theme_display()

    theme_display.short_description = 'Thème'

    def density_display(self, obj):
        return obj.get_density_display()

    density_display.short_description = 'Densité'


@admin.register(DashboardNotification)
class DashboardNotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user_display', 'notification_type_display',
                    'priority_display', 'read', 'created_at']
    list_filter = ['notification_type', 'priority', 'read', 'archived', 'created_at']
    search_fields = ['title', 'message', 'user__email']
    readonly_fields = ['created_at']
    list_editable = ['read']

    fieldsets = (
        ('Destinataire', {
            'fields': ('user',)
        }),
        ('Notification', {
            'fields': ('title', 'message', 'notification_type', 'icon', 'priority')
        }),
        ('Actions', {
            'fields': ('action_url', 'action_label', 'action_data')
        }),
        ('Statut', {
            'fields': ('read', 'archived', 'acknowledged')
        }),
        ('Source', {
            'fields': ('source_module', 'source_id', 'data'),
            'classes': ('collapse',)
        }),
        ('Expiration', {
            'fields': ('expires_at',)
        }),
        ('Création', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    def user_display(self, obj):
        return obj.user.email if obj.user else '-'

    user_display.short_description = 'Utilisateur'

    def notification_type_display(self, obj):
        return obj.get_notification_type_display()

    notification_type_display.short_description = 'Type'

    def priority_display(self, obj):
        colors = {0: 'gray', 1: 'orange', 2: 'red'}
        color = colors.get(obj.priority, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_priority_display()
        )

    priority_display.short_description = 'Priorité'

    actions = ['mark_as_read', 'mark_as_unread', 'archive_selected']

    def mark_as_read(self, request, queryset):
        updated = queryset.update(read=True)
        self.message_user(request, f"{updated} notification(s) marquée(s) comme lue(s)")

    mark_as_read.short_description = "Marquer comme lues"

    def mark_as_unread(self, request, queryset):
        updated = queryset.update(read=False)
        self.message_user(request, f"{updated} notification(s) marquée(s) comme non lue(s)")

    mark_as_unread.short_description = "Marquer comme non lues"

    def archive_selected(self, request, queryset):
        updated = queryset.update(archived=True)
        self.message_user(request, f"{updated} notification(s) archivée(s)")

    archive_selected.short_description = "Archiver les notifications"


@admin.register(DashboardQuickAction)
class DashboardQuickActionAdmin(admin.ModelAdmin):
    list_display = ['name', 'action_type_display', 'enabled', 'visible', 'order', 'category']
    list_filter = ['action_type', 'enabled', 'visible', 'category']
    search_fields = ['name', 'description', 'url']
    list_editable = ['enabled', 'visible', 'order', 'category']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Informations Générales', {
            'fields': ('name', 'action_type', 'description', 'category')
        }),
        ('Apparence', {
            'fields': ('icon', 'color', 'badge_text', 'badge_color')
        }),
        ('Configuration', {
            'fields': ('url', 'method', 'requires_confirmation', 'confirmation_message', 'shortcut_key')
        }),
        ('Permissions', {
            'fields': ('allowed_roles', 'required_permission')
        }),
        ('Visibilité', {
            'fields': ('enabled', 'visible', 'order')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def action_type_display(self, obj):
        return obj.get_action_type_display()

    action_type_display.short_description = 'Type d\'action'


@admin.register(CachedDashboardData)
class CachedDashboardDataAdmin(admin.ModelAdmin):
    list_display = ['cache_key_short', 'cache_type_display', 'expires_at', 'created_at']
    list_filter = ['cache_type', 'expires_at']
    search_fields = ['cache_key', 'cache_type']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Cache', {
            'fields': ('cache_key', 'cache_type', 'version', 'hash')
        }),
        ('Données', {
            'fields': ('data',),
            'classes': ('collapse',)
        }),
        ('Expiration', {
            'fields': ('expires_at',)
        }),
        ('Contexte', {
            'fields': ('user', 'query_params', 'context'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def cache_key_short(self, obj):
        return obj.cache_key[:50] + '...' if len(obj.cache_key) > 50 else obj.cache_key

    cache_key_short.short_description = 'Clé de cache'

    def cache_type_display(self, obj):
        return obj.get_cache_type_display()

    cache_type_display.short_description = 'Type'

    actions = ['clear_expired_cache', 'clear_all_cache']

    def clear_expired_cache(self, request, queryset):
        from django.utils import timezone
        expired = queryset.filter(expires_at__lt=timezone.now()).count()
        queryset.filter(expires_at__lt=timezone.now()).delete()
        self.message_user(request, f"{expired} entrée(s) de cache expirée(s) supprimée(s)")

    clear_expired_cache.short_description = "Supprimer le cache expiré"

    def clear_all_cache(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"{count} entrée(s) de cache supprimée(s)")

    clear_all_cache.short_description = "Supprimer tout le cache"


@admin.register(UserWidgetPreference)
class UserWidgetPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user_display', 'widget_display', 'enabled', 'order']
    list_filter = ['enabled']
    search_fields = ['user_dashboard__user__email', 'widget__name']
    readonly_fields = ['created_at', 'updated_at']

    def user_display(self, obj):
        return obj.user_dashboard.user.email if obj.user_dashboard and obj.user_dashboard.user else '-'

    user_display.short_description = 'Utilisateur'

    def widget_display(self, obj):
        return obj.widget.name if obj.widget else '-'

    widget_display.short_description = 'Widget'


@admin.register(DashboardAnalytics)
class DashboardAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['user_display', 'total_views', 'total_time_spent', 'last_access']
    list_filter = ['last_access']
    search_fields = ['user__email', 'user__username']
    readonly_fields = ['created_at', 'updated_at', 'last_access']

    def user_display(self, obj):
        return obj.user.email if obj.user else '-'

    user_display.short_description = 'Utilisateur'

    fieldsets = (
        ('Utilisateur', {
            'fields': ('user',)
        }),
        ('Statistiques d\'utilisation', {
            'fields': ('total_views', 'total_time_spent', 'avg_session_time')
        }),
        ('Analytics', {
            'fields': ('most_used_widgets', 'most_frequent_actions',
                       'access_frequency', 'detected_preferences'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('last_access', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )