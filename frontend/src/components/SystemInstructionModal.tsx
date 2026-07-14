import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Plus, Trash2, Star, ChevronDown, ChevronUp, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { EllipsisTooltip } from '@/components/EllipsisTooltip';
import { cn } from '@/components/ui/utils';
import { toast } from 'sonner';
import {
  SystemInstructionResponse,
  SystemInstructionCreate,
  SystemInstructionUpdate,
  listSystemInstructions,
  createSystemInstruction,
  updateSystemInstruction,
  deleteSystemInstruction,
  markSystemInstructionAsUsed,
} from '@/services/api';

interface SystemInstructionModalProps {
  isOpen: boolean;
  onClose: () => void;
  isDarkMode: boolean;
  onSelect?: (instruction: SystemInstructionResponse) => void;
  currentInstructionId?: string | null;
}

export function SystemInstructionModal({
  isOpen,
  onClose,
  isDarkMode,
  onSelect,
  currentInstructionId,
}: SystemInstructionModalProps) {
  const { t } = useTranslation();
  const [instructions, setInstructions] = useState<SystemInstructionResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  // Create/edit form
  const [formTitle, setFormTitle] = useState('');
  const [formContent, setFormContent] = useState('');
  const [formIsDefault, setFormIsDefault] = useState(false);

  // Load list
  const loadInstructions = async () => {
    try {
      setIsLoading(true);
      const data = await listSystemInstructions();
      setInstructions(data);
    } catch (error) {
      console.error('Failed to load system instructions:', error);
      toast.error(t('instructions.loadFailed'));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadInstructions();
    }
  }, [isOpen]);

  const handleCreate = () => {
    setIsCreating(true);
    setEditingId(null);
    setFormTitle('');
    setFormContent('');
    setFormIsDefault(false);
  };

  const handleEdit = (instruction: SystemInstructionResponse) => {
    setIsCreating(false);
    setEditingId(instruction.id);
    setFormTitle(instruction.title);
    setFormContent(instruction.content);
    setFormIsDefault(instruction.is_default);
  };

  const handleCancelEdit = () => {
    setIsCreating(false);
    setEditingId(null);
    setFormTitle('');
    setFormContent('');
    setFormIsDefault(false);
  };

  const handleSave = async () => {
    if (!formTitle.trim()) {
      toast.error(t('instructions.titleRequired'));
      return;
    }
    if (!formContent.trim()) {
      toast.error(t('instructions.contentRequired'));
      return;
    }

    try {
      if (editingId) {
        // Update
        const data: SystemInstructionUpdate = {
          title: formTitle,
          content: formContent,
          is_default: formIsDefault,
        };
        await updateSystemInstruction(editingId, data);
        toast.success(t('instructions.updated'));
      } else {
        // Create
        const data: SystemInstructionCreate = {
          title: formTitle,
          content: formContent,
          is_default: formIsDefault,
        };
        await createSystemInstruction(data);
        toast.success(t('instructions.created'));
      }
      handleCancelEdit();
      loadInstructions();
    } catch (error) {
      console.error('Failed to save:', error);
      toast.error(t('instructions.saveFailed'));
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm(t('instructions.confirmDelete'))) {
      return;
    }

    try {
      await deleteSystemInstruction(id);
      toast.success(t('instructions.deleted'));
      loadInstructions();
    } catch (error) {
      console.error('Failed to delete:', error);
      toast.error(t('instructions.deleteFailed'));
    }
  };

  const handleSelect = async (instruction: SystemInstructionResponse) => {
    try {
      await markSystemInstructionAsUsed(instruction.id);
      onSelect?.(instruction);
      toast.success(t('instructions.selected', { title: instruction.title }));
      onClose();
    } catch (error) {
      console.error('Failed to mark as used:', error);
      toast.error(t('instructions.selectFailed'));
    }
  };

  const handleSetDefault = async (id: string) => {
    try {
      await updateSystemInstruction(id, { is_default: true });
      toast.success(t('instructions.markedDefault'));
      loadInstructions();
    } catch (error) {
      console.error('Failed to set default:', error);
      toast.error(t('instructions.markDefaultFailed'));
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200 p-0 sm:p-4",
        isDarkMode && "dark"
      )}
    >
      <div
        className="w-full sm:w-[600px] sm:max-w-[calc(100vw-2rem)] max-h-[92dvh] sm:max-h-[90vh] rounded-t-2xl sm:rounded-2xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-200 transition-colors"
        style={{
          backgroundColor: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          boxShadow: isDarkMode
            ? '0 25px 50px -12px rgba(0, 0, 0, 0.7)'
            : '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-[var(--border-color)]">
          <div className="flex flex-col gap-0.5">
            <h2 className="text-lg font-semibold text-[var(--text-primary)] tracking-tight">
              {t('instructions.title')}
            </h2>
            <p className="text-xs text-[var(--text-secondary)]">
              {t('instructions.subtitle')}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors rounded-full p-1 hover:bg-[var(--bg-hover)]"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto custom-scrollbar bg-[var(--bg-main)]">
          <div className="p-4 sm:p-6 space-y-4">
            {/* Create Button */}
            {!isCreating && !editingId && (
              <button
                onClick={handleCreate}
                className="w-full flex items-center gap-2 px-4 py-3 rounded-lg border-2 border-dashed border-[var(--border-color)] hover:border-blue-500 hover:bg-blue-500/5 transition-all text-[var(--text-secondary)] hover:text-blue-500 group"
              >
                <Plus size={18} className="group-hover:scale-110 transition-transform" />
                <span className="text-sm font-medium">{t('instructions.createNew')}</span>
              </button>
            )}

            {/* Create/Edit Form */}
            {(isCreating || editingId) && (
              <div className="space-y-3 p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] shadow-sm">
                {/* Title Input */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">
                    {t('instructions.formTitleLabel')}
                  </label>
                  <input
                    type="text"
                    value={formTitle}
                    onChange={(e) => setFormTitle(e.target.value)}
                    placeholder={t('instructions.formTitlePlaceholder')}
                    className="w-full bg-[var(--bg-input)] border border-[var(--border-color)] rounded-lg h-10 px-3 text-sm text-[var(--text-primary)] focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-[var(--text-placeholder)]"
                  />
                </div>

                {/* Content Textarea */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">
                    {t('instructions.formContentLabel')}
                  </label>
                  <textarea
                    value={formContent}
                    onChange={(e) => setFormContent(e.target.value)}
                    placeholder={t('instructions.formContentPlaceholder')}
                    rows={8}
                    className="w-full bg-[var(--bg-input)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-[var(--text-placeholder)] resize-none custom-scrollbar"
                  />
                </div>

                {/* Default Checkbox */}
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="is-default"
                    checked={formIsDefault}
                    onChange={(e) => setFormIsDefault(e.target.checked)}
                    className="w-4 h-4 rounded border-[var(--border-color)] text-blue-500 focus:ring-blue-500"
                  />
                  <label
                    htmlFor="is-default"
                    className="text-sm text-[var(--text-secondary)] cursor-pointer select-none"
                  >
                    {t('instructions.setAsDefault')}
                  </label>
                </div>

                {/* Form Actions */}
                <div className="flex items-center gap-2 pt-2">
                  <Button
                    onClick={handleSave}
                    className="flex-1 bg-blue-600 hover:bg-blue-700 text-white dark:bg-[#A8C7FA] dark:hover:bg-[#8AB4F8] dark:text-[#000] font-medium h-9"
                  >
                    {editingId ? t('common.update') : t('common.create')}
                  </Button>
                  <Button
                    onClick={handleCancelEdit}
                    variant="ghost"
                    className="flex-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] h-9"
                  >
                    {t('common.cancel')}
                  </Button>
                </div>
              </div>
            )}

            {/* Instructions List */}
            {!isCreating && !editingId && (
              <div className="space-y-2">
                {isLoading ? (
                  <div className="text-center py-8 text-[var(--text-secondary)]">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
                    <p className="mt-2 text-sm">{t('common.loading')}</p>
                  </div>
                ) : instructions.length === 0 ? (
                  <div className="text-center py-12 text-[var(--text-secondary)]">
                    <p className="text-sm">{t('instructions.empty')}</p>
                    <p className="text-xs mt-1">{t('instructions.emptyHint')}</p>
                  </div>
                ) : (
                  instructions.map((instruction) => (
                    <InstructionItem
                      key={instruction.id}
                      instruction={instruction}
                      isDarkMode={isDarkMode}
                      isSelected={currentInstructionId === instruction.id}
                      onEdit={handleEdit}
                      onDelete={handleDelete}
                      onSelect={handleSelect}
                      onSetDefault={handleSetDefault}
                    />
                  ))
                )}
              </div>
            )}
          </div>
        </div>

        {/* Footer Note */}
        <div className="px-4 sm:px-6 py-3 border-t border-[var(--border-color)] bg-[var(--bg-card)]">
          <p className="text-[10px] text-[var(--text-secondary)]">
            {t('instructions.footerNote')}
          </p>
        </div>
      </div>
    </div>
  );
}

// Instruction Item Component
interface InstructionItemProps {
  instruction: SystemInstructionResponse;
  isDarkMode: boolean;
  isSelected: boolean;
  onEdit: (instruction: SystemInstructionResponse) => void;
  onDelete: (id: string) => void;
  onSelect: (instruction: SystemInstructionResponse) => void;
  onSetDefault: (id: string) => void;
}

function InstructionItem({
  instruction,
  isDarkMode,
  isSelected,
  onEdit,
  onDelete,
  onSelect,
  onSetDefault,
}: InstructionItemProps) {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div
      className={cn(
        'group rounded-lg border transition-all duration-200',
        isSelected
          ? 'border-blue-500 bg-blue-500/5'
          : 'border-[var(--border-color)] hover:border-[var(--border-hover)] bg-[var(--bg-card)]'
      )}
    >
      {/* Header */}
      <div className="flex items-start gap-3 p-3">
        {/* Icon */}
        <div className="flex-shrink-0 mt-0.5">
          {instruction.is_default ? (
            <Star size={16} className="text-yellow-500 fill-yellow-500" />
          ) : (
            <div className="w-4 h-4 rounded-full border-2 border-[var(--border-color)]" />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <EllipsisTooltip as="h3" className="text-sm font-semibold text-[var(--text-primary)]">
                {instruction.title}
              </EllipsisTooltip>
              <p
                className={cn(
                  'text-xs text-[var(--text-secondary)] mt-1 transition-all',
                  isExpanded ? 'line-clamp-none' : 'line-clamp-2'
                )}
              >
                {instruction.content}
              </p>
            </div>

            {/* Expand Button */}
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="flex-shrink-0 p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] rounded transition-colors"
            >
              {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={() => onSelect(instruction)}
              className="text-xs px-2 py-1 rounded bg-blue-500 hover:bg-blue-600 text-white font-medium transition-colors flex items-center gap-1"
            >
              <Check size={12} />
              {t('instructions.select')}
            </button>
            {!instruction.is_default && (
              <button
                onClick={() => onSetDefault(instruction.id)}
                className="text-xs px-2 py-1 rounded border border-[var(--border-color)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
              >
                {t('instructions.setDefaultBtn')}
              </button>
            )}
            <button
              onClick={() => onEdit(instruction)}
              className="text-xs px-2 py-1 rounded border border-[var(--border-color)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            >
              {t('instructions.edit')}
            </button>
            <button
              onClick={() => onDelete(instruction.id)}
              className="text-xs px-2 py-1 rounded hover:bg-red-500/10 text-[var(--text-secondary)] hover:text-red-500 transition-colors"
            >
              <Trash2 size={12} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
