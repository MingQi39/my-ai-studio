import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, Trash2, MessageSquare, Calendar } from 'lucide-react';
import { SessionResponse, listSessions, deleteSession as apiDeleteSession } from '@/services/api';
import { toast } from 'sonner';
import { ScrollArea } from '@/components/ui/scroll-area';

interface SessionHistoryProps {
    onSelectSession: (sessionId: string) => void;
    currentSessionId: string | null;
    isDarkMode: boolean;
}

export function SessionHistory({ onSelectSession, currentSessionId, isDarkMode }: SessionHistoryProps) {
    const { t, i18n } = useTranslation();
    const [sessions, setSessions] = useState<SessionResponse[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    // Load session list
    const loadSessions = async () => {
        try {
            setIsLoading(true);
            const response = await listSessions(1, 100, false); // first 100, exclude archived
            setSessions(response.items);
        } catch (error) {
            console.error('Failed to load sessions:', error);
            toast.error(t('sessionHistory.loadFailed'));
        } finally {
            setIsLoading(false);
        }
    };

    // Initial load
    useEffect(() => {
        loadSessions();
    }, []);

    // Delete session
    const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
        e.stopPropagation();

        if (!confirm(t('sessionHistory.confirmDelete'))) {
            return;
        }

        try {
            await apiDeleteSession(sessionId);
            setSessions(prev => prev.filter(s => s.id !== sessionId));

            // If the deleted session was current, clear selection
            if (currentSessionId === sessionId) {
                onSelectSession('');
            }

            toast.success(t('sessionHistory.deleted'));
        } catch (error) {
            console.error('Failed to delete session:', error);
            toast.error(t('sessionHistory.deleteFailed'));
        }
    };

    // Format date
    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        const now = new Date();
        const diff = now.getTime() - date.getTime();
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));

        if (days === 0) {
            return t('common.today');
        } else if (days === 1) {
            return t('common.yesterday');
        } else if (days < 7) {
            return t('common.daysAgo', { count: days });
        } else {
            return date.toLocaleDateString(i18n.language, { month: 'short', day: 'numeric' });
        }
    };

    // Group sessions: today, yesterday, last 7 days, earlier
    const groupSessions = () => {
        const now = new Date();
        const today: SessionResponse[] = [];
        const yesterday: SessionResponse[] = [];
        const thisWeek: SessionResponse[] = [];
        const earlier: SessionResponse[] = [];

        sessions.forEach(session => {
            const sessionDate = new Date(session.updated_at);
            const diffDays = Math.floor((now.getTime() - sessionDate.getTime()) / (1000 * 60 * 60 * 24));

            if (diffDays === 0) {
                today.push(session);
            } else if (diffDays === 1) {
                yesterday.push(session);
            } else if (diffDays < 7) {
                thisWeek.push(session);
            } else {
                earlier.push(session);
            }
        });

        const groups: { title: string; sessions: SessionResponse[] }[] = [];
        if (today.length > 0) groups.push({ title: t('sessionHistory.today'), sessions: today });
        if (yesterday.length > 0) groups.push({ title: t('sessionHistory.yesterday'), sessions: yesterday });
        if (thisWeek.length > 0) groups.push({ title: t('sessionHistory.thisWeek'), sessions: thisWeek });
        if (earlier.length > 0) groups.push({ title: t('sessionHistory.earlier'), sessions: earlier });

        return groups;
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="flex flex-col items-center gap-3">
                    <Loader2 size={24} className="animate-spin text-[var(--text-secondary)]" />
                    <p className="text-sm text-[var(--text-secondary)]">{t('sessionHistory.loadingList')}</p>
                </div>
            </div>
        );
    }

    if (sessions.length === 0) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="flex flex-col items-center gap-3 text-center px-6">
                    <MessageSquare size={48} className="text-[var(--text-secondary)] opacity-30" />
                    <div>
                        <p className="text-base font-medium text-[var(--text-primary)] mb-1">{t('sessionHistory.empty')}</p>
                        <p className="text-sm text-[var(--text-secondary)]">{t('sessionHistory.emptyHint')}</p>
                    </div>
                </div>
            </div>
        );
    }

    const groupedSessions = groupSessions();

    return (
        <div className="flex flex-col h-full bg-[var(--bg-main)]">
            {/* Header */}
            <div className="flex-shrink-0 px-6 py-4 border-b border-[var(--border-color)]">
                <h2 className="text-lg font-semibold text-[var(--text-primary)]">{t('sessionHistory.title')}</h2>
                <p className="text-sm text-[var(--text-secondary)] mt-1">{t('sessionHistory.totalCount', { count: sessions.length })}</p>
            </div>

            {/* Session list */}
            <ScrollArea className="flex-1 custom-scrollbar">
                <div className="px-4 py-4">
                    {groupedSessions.map((group, groupIndex) => (
                        <div key={groupIndex} className="mb-6">
                            {/* Group title */}
                            <div className="flex items-center gap-2 px-2 py-2 mb-2">
                                <Calendar size={14} className="text-[var(--text-secondary)]" />
                                <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
                                    {group.title}
                                </h3>
                            </div>

                            {/* Sessions in group */}
                            <div className="space-y-1">
                                {group.sessions.map((session) => {
                                    const isActive = currentSessionId === session.id;

                                    return (
                                        <div
                                            key={session.id}
                                            onClick={() => onSelectSession(session.id)}
                                            className={`
                        relative group flex items-center gap-3 px-3 py-3 rounded-lg cursor-pointer
                        transition-all duration-200
                        ${isActive
                                                    ? 'bg-[var(--nav-active-bg)] text-[var(--nav-active-text)]'
                                                    : 'hover:bg-[var(--bg-hover)] text-[var(--text-primary)]'
                                                }
                      `}
                                        >
                                            {/* Active indicator */}
                                            {isActive && (
                                                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-blue-500 rounded-r-full" />
                                            )}

                                            {/* Message icon */}
                                            <div className={`
                        flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center
                        ${isActive ? 'bg-blue-500/20' : 'bg-[var(--bg-card)]'}
                      `}>
                                                <MessageSquare
                                                    size={16}
                                                    className={isActive ? 'text-blue-500' : 'text-[var(--text-secondary)]'}
                                                />
                                            </div>

                                            {/* Session info */}
                                            <div className="flex-1 min-w-0">
                                                <p className={`
                          text-sm font-medium truncate
                          ${isActive ? 'text-[var(--nav-active-text)]' : 'text-[var(--text-primary)]'}
                        `}>
                                                    {session.title || t('sessionHistory.untitled')}
                                                </p>
                                                <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                                                    {t('sessionHistory.messages', { count: session.message_count })} · {formatDate(session.updated_at)}
                                                </p>
                                            </div>

                                            {/* Delete button */}
                                            <button
                                                onClick={(e) => handleDeleteSession(session.id, e)}
                                                className={`
                          flex-shrink-0 p-1.5 rounded-md transition-all
                          opacity-0 group-hover:opacity-100
                          hover:bg-red-500/10 text-[var(--text-secondary)] hover:text-red-500
                        `}
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    ))}
                </div>
            </ScrollArea>
        </div>
    );
}
