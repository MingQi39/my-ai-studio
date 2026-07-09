import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, Loader2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ConfirmDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void | Promise<void>;
    title: string;
    message: string;
    confirmText?: string;
    cancelText?: string;
    isDarkMode?: boolean;
    type?: 'danger' | 'warning' | 'info';
}

export function ConfirmDialog({
    isOpen,
    onClose,
    onConfirm,
    title,
    message,
    confirmText,
    cancelText,
    isDarkMode = false,
    type = 'danger'
}: ConfirmDialogProps) {
    const { t } = useTranslation();
    const [isConfirming, setIsConfirming] = useState(false);
    const safeConfirm = confirmText ?? t('common.confirm');
    const safeCancel = cancelText ?? t('common.cancel');

    useEffect(() => {
        if (!isOpen) setIsConfirming(false);
    }, [isOpen]);

    if (!isOpen) return null;

    const handleConfirm = async () => {
        if (isConfirming) return;
        setIsConfirming(true);
        try {
            await onConfirm();
            onClose();
        } finally {
            setIsConfirming(false);
        }
    };

    const getTypeColor = () => {
        switch (type) {
            case 'danger':
                return 'text-red-500';
            case 'warning':
                return 'text-orange-500';
            case 'info':
                return 'text-blue-500';
            default:
                return 'text-red-500';
        }
    };

    return (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 animate-in fade-in duration-200"
                onClick={isConfirming ? undefined : onClose}
            />

            {/* Dialog */}
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
                <div
                    className="pointer-events-auto w-full max-w-md rounded-2xl shadow-2xl animate-in zoom-in-95 duration-200"
                    style={{
                        backgroundColor: 'var(--bg-card)',
                        border: '1px solid var(--border-color)',
                    }}
                    onClick={(e) => e.stopPropagation()}
                >
                    {/* Header */}
                    <div className="flex items-start gap-3 sm:gap-4 p-4 sm:p-6 pb-4">
                        <div
                            className={`flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center ${type === 'danger' ? 'bg-red-500/10' : type === 'warning' ? 'bg-orange-500/10' : 'bg-blue-500/10'
                                }`}
                        >
                            <AlertTriangle size={24} className={getTypeColor()} />
                        </div>
                        {/* Title and close */}
                        <div className="flex-1">
                            <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                                {title}
                            </h3>
                            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
                                {message}
                            </p>
                        </div>
                        {/* Close button */}
                        <button
                            onClick={onClose}
                            disabled={isConfirming}
                            className="flex-shrink-0 p-1 rounded-lg hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors disabled:opacity-50 disabled:pointer-events-none"
                        >
                            <X size={20} />
                        </button>
                    </div>

                    {/* Footer buttons */}
                    <div className="flex items-center gap-3 px-4 sm:px-6 pb-4 sm:pb-6 pt-2">
                        <Button
                            onClick={onClose}
                            variant="ghost"
                            disabled={isConfirming}
                            className="flex-1 h-10 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                        >
                            {safeCancel}
                        </Button>
                        <Button
                            onClick={handleConfirm}
                            disabled={isConfirming}
                            className={`flex-1 h-10 rounded-lg font-medium ${type === 'danger'
                                    ? 'bg-red-500 hover:bg-red-600 text-white'
                                    : type === 'warning'
                                        ? 'bg-orange-500 hover:bg-orange-600 text-white'
                                        : 'bg-blue-500 hover:bg-blue-600 text-white'
                                }`}
                        >
                            {isConfirming ? <Loader2 size={16} className="animate-spin" /> : safeConfirm}
                        </Button>
                    </div>
                </div>
            </div>
        </>
    );
}
