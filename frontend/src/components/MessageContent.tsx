import React, { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus, vs } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Copy, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface MessageContentProps {
    content: string;
    isStreaming?: boolean;
    typewriterSpeed?: number; // characters per second
    isDarkMode?: boolean;
}

export function MessageContent({
    content,
    isStreaming = false,
    typewriterSpeed = 30,
    isDarkMode = false
}: MessageContentProps) {
    const { t } = useTranslation();
    const [displayedContent, setDisplayedContent] = useState('');
    const [copiedCode, setCopiedCode] = useState<string | null>(null);

    // Typewriter effect for streaming messages
    useEffect(() => {
        // Skip typewriter for non-streaming or very long content
        if (!isStreaming || content.length > 5000) {
            setDisplayedContent(content);
            return;
        }

        // Typewriter animation
        let currentIndex = displayedContent.length;

        const timer = setInterval(() => {
            if (currentIndex < content.length) {
                setDisplayedContent(content.slice(0, currentIndex + 1));
                currentIndex++;
            } else {
                clearInterval(timer);
            }
        }, 1000 / typewriterSpeed);

        return () => clearInterval(timer);
    }, [content, isStreaming, typewriterSpeed]);

    // Copy code to clipboard
    const handleCopyCode = async (code: string, language: string) => {
        await navigator.clipboard.writeText(code);
        setCopiedCode(`${language}-${code.substring(0, 20)}`);
        setTimeout(() => setCopiedCode(null), 2000);
    };

    // Memoize markdown rendering for performance
    const renderedContent = useMemo(() => {
        return (
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    // Custom code block rendering with syntax highlighting
                    code({ node, inline, className, children, ...props }) {
                        const match = /language-(\w+)/.exec(className || '');
                        const code = String(children).replace(/\n$/, '');
                        const language = match ? match[1] : 'text';
                        const codeId = `${language}-${code.substring(0, 20)}`;
                        const isCopied = copiedCode === codeId;

                        if (!inline && match) {
                            return (
                                <div style={{ position: 'relative', marginTop: '1rem', marginBottom: '1rem' }}>
                                    {/* Language label and copy button */}
                                    <div style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'space-between',
                                        padding: '0.5rem 1rem',
                                        backgroundColor: 'var(--bg-hover)',
                                        borderBottom: '1px solid var(--border-color)',
                                        borderTopLeftRadius: '8px',
                                        borderTopRightRadius: '8px'
                                    }}>
                                        <span style={{
                                            fontSize: '0.75rem',
                                            fontFamily: 'monospace',
                                            color: 'var(--text-secondary)',
                                            textTransform: 'uppercase'
                                        }}>
                                            {language}
                                        </span>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => handleCopyCode(code, language)}
                                            style={{ height: '1.75rem', padding: '0 0.5rem' }}
                                        >
                                            {isCopied ? (
                                                <>
                                                    <Check size={14} style={{ marginRight: '0.25rem' }} />
                                                    {t('messageContent.copied')}
                                                </>
                                            ) : (
                                                <>
                                                    <Copy size={14} style={{ marginRight: '0.25rem' }} />
                                                    {t('messageContent.copy')}
                                                </>
                                            )}
                                        </Button>
                                    </div>

                                    {/* Code block with syntax highlighting */}
                                    <SyntaxHighlighter
                                        style={isDarkMode ? vscDarkPlus : vs}
                                        language={language}
                                        PreTag="div"
                                        customStyle={{
                                            marginTop: 0,
                                            borderTopLeftRadius: 0,
                                            borderTopRightRadius: 0,
                                            borderBottomLeftRadius: '8px',
                                            borderBottomRightRadius: '8px'
                                        }}
                                    >
                                        {code}
                                    </SyntaxHighlighter>
                                </div>
                            );
                        }

                        // Inline code
                        return (
                            <code
                                style={{
                                    padding: '2px 6px',
                                    borderRadius: '4px',
                                    backgroundColor: 'var(--bg-hover)',
                                    color: 'var(--text-primary)',
                                    fontFamily: 'monospace',
                                    fontSize: '0.875rem'
                                }}
                            >
                                {children}
                            </code>
                        );
                    },

                    // Headings
                    h1: ({ children }) => (
                        <h1 style={{
                            fontSize: '1.5rem',
                            fontWeight: 'bold',
                            marginTop: '1.5rem',
                            marginBottom: '1rem',
                            color: 'var(--text-primary)',
                            borderBottom: '1px solid var(--border-color)',
                            paddingBottom: '0.5rem'
                        }}>
                            {children}
                        </h1>
                    ),
                    h2: ({ children }) => (
                        <h2 style={{
                            fontSize: '1.25rem',
                            fontWeight: 'bold',
                            marginTop: '1.25rem',
                            marginBottom: '0.75rem',
                            color: 'var(--text-primary)'
                        }}>
                            {children}
                        </h2>
                    ),
                    h3: ({ children }) => (
                        <h3 style={{
                            fontSize: '1.125rem',
                            fontWeight: '600',
                            marginTop: '1rem',
                            marginBottom: '0.5rem',
                            color: 'var(--text-primary)'
                        }}>
                            {children}
                        </h3>
                    ),

                    // Lists
                    ul: ({ children }) => (
                        <ul style={{
                            listStyleType: 'disc',
                            listStylePosition: 'outside',
                            marginLeft: '1.5rem',
                            marginTop: '0.75rem',
                            marginBottom: '0.75rem',
                            color: 'var(--text-primary)'
                        }}>
                            {children}
                        </ul>
                    ),
                    ol: ({ children }) => (
                        <ol style={{
                            listStyleType: 'decimal',
                            listStylePosition: 'outside',
                            marginLeft: '1.5rem',
                            marginTop: '0.75rem',
                            marginBottom: '0.75rem',
                            color: 'var(--text-primary)'
                        }}>
                            {children}
                        </ol>
                    ),

                    // Links
                    a: ({ href, children }) => (
                        <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                                color: '#3b82f6',
                                textDecoration: 'underline',
                                textUnderlineOffset: '2px'
                            }}
                        >
                            {children}
                        </a>
                    ),

                    // Blockquotes
                    blockquote: ({ children }) => (
                        <blockquote style={{
                            borderLeft: '4px solid var(--border-color)',
                            paddingLeft: '1rem',
                            marginTop: '0.75rem',
                            marginBottom: '0.75rem',
                            fontStyle: 'italic',
                            color: 'var(--text-secondary)'
                        }}>
                            {children}
                        </blockquote>
                    ),

                    // Tables
                    table: ({ children }) => (
                        <div style={{ overflowX: 'auto', marginTop: '1rem', marginBottom: '1rem' }}>
                            <table style={{
                                minWidth: '100%',
                                border: '1px solid var(--border-color)',
                                borderRadius: '8px',
                                borderCollapse: 'collapse'
                            }}>
                                {children}
                            </table>
                        </div>
                    ),
                    thead: ({ children }) => (
                        <thead style={{ backgroundColor: 'var(--bg-hover)' }}>
                            {children}
                        </thead>
                    ),
                    th: ({ children }) => (
                        <th style={{
                            padding: '0.5rem 1rem',
                            textAlign: 'left',
                            fontSize: '0.875rem',
                            fontWeight: '600',
                            color: 'var(--text-primary)',
                            borderBottom: '1px solid var(--border-color)'
                        }}>
                            {children}
                        </th>
                    ),
                    td: ({ children }) => (
                        <td style={{
                            padding: '0.5rem 1rem',
                            fontSize: '0.875rem',
                            color: 'var(--text-primary)',
                            borderBottom: '1px solid var(--border-color)'
                        }}>
                            {children}
                        </td>
                    ),

                    // Paragraphs
                    p: ({ children }) => (
                        <p style={{
                            marginTop: '0.75rem',
                            marginBottom: '0.75rem',
                            lineHeight: '1.75',
                            color: 'var(--text-primary)'
                        }}>
                            {children}
                        </p>
                    ),
                }}
            >
                {displayedContent}
            </ReactMarkdown>
        );
    }, [displayedContent, isDarkMode, copiedCode, handleCopyCode, t]);

    return (
        <div style={{ color: 'var(--text-primary)', lineHeight: '1.75' }}>
            {renderedContent}
            {isStreaming && displayedContent.length < content.length && (
                <span style={{
                    display: 'inline-block',
                    width: '2px',
                    height: '1.25rem',
                    backgroundColor: 'var(--text-primary)',
                    animation: 'pulse 1s infinite',
                    marginLeft: '2px'
                }} />
            )}
        </div>
    );
}
