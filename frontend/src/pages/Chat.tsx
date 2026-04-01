import { useState, useRef, useEffect, useMemo } from 'react';
import { Bot, User, Send, Plus, ThumbsUp, ThumbsDown, Archive, Trash2, Search, X, ChevronDown, ChevronRight, Brain } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '../lib/utils';
import {
  queryRAGStream,
  listConversations,
  createConversation,
  createFeedback,
  getConversationMessages,
  deleteConversation,
  archiveConversation,
  updateConversationTags,
} from '../lib/api';
import type { Conversation } from '../types';

function unescapeLiteralNewlines(text: string): string {
  return text.replace(/\\n/g, '\n').replace(/\\t/g, '\t').replace(/\\r/g, '\r');
}

interface Message {
  id: string;
  role: 'user' | 'model';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  thinking?: string;
  isThinkingExpanded?: boolean;
}

function ThinkingBlock({ content, isExpanded, onToggle }: { content: string; isExpanded: boolean; onToggle: () => void }) {
  const summary = useMemo(() => {
    const text = unescapeLiteralNewlines(content).trim();
    const firstLine = text.split('\n')[0];
    return firstLine.length > 80 ? firstLine.slice(0, 80) + '...' : firstLine;
  }, [content]);

  return (
    <div className="thinking-block mb-2">
      <button
        onClick={onToggle}
        className="thinking-toggle flex items-center gap-1.5 text-xs text-[var(--color-text-sec)] hover:text-[var(--color-primary)] transition-colors w-full text-left py-1"
      >
        <Brain className="w-3.5 h-3.5 flex-shrink-0" />
        {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        <span className="truncate">{summary}</span>
      </button>
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="thinking-content mt-1 pl-5 text-xs text-[var(--color-text-sec)] leading-relaxed border-l-2 border-[var(--color-border)]">
              {unescapeLiteralNewlines(content)}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

interface ConversationExt extends Conversation {
  isArchived?: boolean;
  tags?: string[];
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'model',
      content:
        "Hello! I'm the RAG Knowledge Base assistant. I can help you query information from the knowledge base. How can I assist you?",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [conversations, setConversations] = useState<ConversationExt[]>([]);
  const [currentConversation, setCurrentConversation] = useState<ConversationExt | null>(null);
  const [feedbackSent, setFeedbackSent] = useState<Record<string, boolean>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [sidebarTab, setSidebarTab] = useState<'recent' | 'archived'>('recent');
  const [searchQuery, setSearchQuery] = useState('');

  const [archiveModalOpen, setArchiveModalOpen] = useState(false);
  const [convToArchive, setConvToArchive] = useState<string | null>(null);
  const [newTag, setNewTag] = useState('');
  const [tempTags, setTempTags] = useState<string[]>([]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const loadConversations = async () => {
    try {
      const convs = await listConversations();
      setConversations(
        convs.map((c) => ({
          ...c,
          isArchived: (c as any).is_archived || false,
          tags: (c as any).tags || [],
        })),
      );
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const handleNewConversation = async () => {
    try {
      const newConv = await createConversation();
      const ext: ConversationExt = { ...newConv, isArchived: false, tags: [] };
      setConversations([ext, ...conversations]);
      setCurrentConversation(ext);
      setMessages([
        {
          id: 'welcome',
          role: 'model',
          content:
            "Hello! I'm the RAG Knowledge Base assistant. I can help you query information from the knowledge base. How can I assist you?",
          timestamp: new Date(),
        },
      ]);
      setFeedbackSent({});
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectConversation = async (conv: ConversationExt) => {
    if (currentConversation?.id === conv.id) return;
    setCurrentConversation(conv);
    try {
      const msgs = await getConversationMessages(conv.id);
      if (msgs.length > 0) {
        setMessages(
          msgs.map((m) => ({
            id: m.id || crypto.randomUUID(),
            role: m.role === 'assistant' ? ('model' as const) : (m.role as 'user' | 'model'),
            content: m.content,
            timestamp: new Date(m.created_at),
          })),
        );
      } else {
        setMessages([
          {
            id: 'welcome',
            role: 'model',
            content:
              "Hello! I'm the RAG Knowledge Base assistant. I can help you query information from the knowledge base. How can I assist you?",
            timestamp: new Date(),
          },
        ]);
      }
      setFeedbackSent({});
    } catch (error) {
      console.error('Failed to load conversation messages:', error);
    }
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    const queryText = input;

    let convId = currentConversation?.id;
    if (!convId) {
      try {
        const newConv = await createConversation(queryText.slice(0, 20) + '...');
        const ext: ConversationExt = { ...newConv, isArchived: false, tags: [] };
        setConversations([ext, ...conversations]);
        setCurrentConversation(ext);
        convId = newConv.id;
      } catch (error) {
        console.error('Failed to create conversation:', error);
      }
    }

    const userMsgId = crypto.randomUUID();
    const userMsg: Message = {
      id: userMsgId,
      role: 'user',
      content: queryText,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    try {
      const modelMsgId = crypto.randomUUID();
      setMessages((prev) => [
        ...prev,
        {
          id: modelMsgId,
          role: 'model',
          content: '',
          timestamp: new Date(),
          isStreaming: true,
          thinking: '',
          isThinkingExpanded: false,
        },
      ]);

      let fullText = '';
      let fullThinking = '';
      for await (const event of queryRAGStream(queryText, 5, convId)) {
        if (event.type === 'thinking') {
          fullThinking += event.data;
        } else if (event.type === 'content') {
          fullText += unescapeLiteralNewlines(event.data);
        } else if (event.type === 'done') {
          try {
            const doneData = JSON.parse(event.data);
            if (doneData.conversation_id && convId !== doneData.conversation_id) {
              convId = doneData.conversation_id;
              setCurrentConversation((prev) => (prev ? { ...prev, id: doneData.conversation_id } : null));
            }
          } catch {
          }
        }
        setMessages((prev) =>
          prev.map((m) =>
            m.id === modelMsgId
              ? { ...m, content: fullText, thinking: fullThinking || undefined }
              : m,
          ),
        );
      }

      setMessages((prev) =>
        prev.map((m) =>
          m.id === modelMsgId
            ? { ...m, isStreaming: false, content: fullText, thinking: fullThinking || undefined }
            : m,
        ),
      );
    } catch (error) {
      console.error('Error generating response:', error);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'model',
          content: 'Sorry, I encountered an error processing your request.',
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleFeedback = async (messageId: string, helpful: boolean) => {
    if (feedbackSent[messageId]) return;

    const message = messages.find((m) => m.id === messageId);
    if (!message || message.role !== 'model') return;

    setFeedbackSent((prev) => ({ ...prev, [messageId]: true }));

    try {
      await createFeedback({
        query: messages[messages.indexOf(message) - 1]?.content || '',
        rating: helpful ? 5 : 1,
        answer: message.content,
        helpful,
      });
    } catch (error) {
      console.error('Failed to submit feedback:', error);
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const deleteConv = async (id: string) => {
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (currentConversation?.id === id) {
        setCurrentConversation(null);
        setMessages([
          {
            id: 'welcome',
            role: 'model',
            content:
              "Hello! I'm the RAG Knowledge Base assistant. I can help you query information from the knowledge base. How can I assist you?",
            timestamp: new Date(),
          },
        ]);
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  const openArchiveModal = (id: string) => {
    setConvToArchive(id);
    setTempTags([]);
    setNewTag('');
    setArchiveModalOpen(true);
  };

  const addTempTag = () => {
    if (newTag.trim() && !tempTags.includes(newTag.trim())) {
      setTempTags((prev) => [...prev, newTag.trim()]);
      setNewTag('');
    }
  };

  const confirmArchive = async () => {
    if (!convToArchive) return;
    try {
      await archiveConversation(convToArchive, { is_archived: true });
      if (tempTags.length > 0) {
        await updateConversationTags(convToArchive, { tags: tempTags });
      }
      setConversations((prev) =>
        prev.map((c) => (c.id === convToArchive ? { ...c, isArchived: true, tags: tempTags } : c)),
      );
    } catch (error) {
      console.error('Failed to archive conversation:', error);
    }
    setArchiveModalOpen(false);
    setConvToArchive(null);
  };

  const filteredConversations = conversations.filter((c) => {
    if (sidebarTab === 'recent') return !c.isArchived;
    if (sidebarTab === 'archived') {
      if (!c.isArchived) return false;
      if (!searchQuery) return true;
      const query = searchQuery.toLowerCase();
      return (
        c.title.toLowerCase().includes(query) || (c.tags && c.tags.some((t) => t.toLowerCase().includes(query)))
      );
    }
    return true;
  });

  return (
    <div className="flex w-full h-full overflow-hidden bg-[var(--color-bg)] relative">
      {/* Archive Modal */}
      <AnimatePresence>
        {archiveModalOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.95 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.95 }}
              className="bg-[var(--color-surface)] rounded-lg shadow-xl w-full max-w-sm p-5 border border-[var(--color-border)]"
            >
              <h3 className="text-lg font-semibold text-[var(--color-text-main)] mb-4">Archive Conversation</h3>
              <div className="mb-4">
                <label className="block text-xs font-medium text-[var(--color-text-sec)] mb-1">Add Tags</label>
                <div className="flex gap-2 mb-2">
                  <input
                    type="text"
                    value={newTag}
                    onChange={(e) => setNewTag(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        addTempTag();
                        e.preventDefault();
                      }
                    }}
                    placeholder="e.g. finance, report"
                    className="flex-1 h-8 px-2 text-sm border border-[var(--color-border)] rounded bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-primary)] text-[var(--color-text-main)]"
                  />
                  <button
                    onClick={addTempTag}
                    className="px-3 h-8 bg-[var(--color-bg)] border border-[var(--color-border)] rounded text-xs hover:bg-[var(--color-border)] text-[var(--color-text-main)] transition-colors"
                  >
                    Add
                  </button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {tempTags.map((tag) => (
                    <span
                      key={tag}
                      className="text-xs px-2 py-1 bg-[var(--color-primary)]/10 text-[var(--color-primary)] rounded-md flex items-center gap-1"
                    >
                      {tag}
                      <button
                        onClick={() => setTempTags((prev) => prev.filter((t) => t !== tag))}
                        className="hover:text-[var(--color-primary-hover)]"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-6">
                <button
                  onClick={() => setArchiveModalOpen(false)}
                  className="px-4 py-2 text-sm text-[var(--color-text-sec)] hover:bg-[var(--color-bg)] rounded-md transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={confirmArchive}
                  className="px-4 py-2 text-sm bg-[var(--color-primary)] text-white rounded-md hover:bg-[var(--color-primary-hover)] transition-colors"
                >
                  Archive
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Left Sidebar - History */}
      <div className="w-[280px] flex-shrink-0 border-r border-[var(--color-border)] bg-[var(--color-surface)] flex flex-col hidden md:flex">
        <div className="p-4 border-b border-[var(--color-border)]">
          <button
            onClick={handleNewConversation}
            className="w-full h-8 bg-[var(--color-primary)] text-white text-xs rounded-md flex items-center justify-center gap-2 hover:bg-[var(--color-primary-hover)] transition-colors mb-3"
          >
            <Plus className="w-4 h-4" /> New Conversation
          </button>
          <div className="flex bg-[var(--color-bg)] p-1 rounded-md">
            <button
              onClick={() => setSidebarTab('recent')}
              className={cn(
                'flex-1 text-xs py-1.5 rounded-sm text-center transition-colors',
                sidebarTab === 'recent'
                  ? 'bg-[var(--color-surface)] shadow-sm text-[var(--color-text-main)]'
                  : 'text-[var(--color-text-sec)] hover:text-[var(--color-text-main)]',
              )}
            >
              Recent
            </button>
            <button
              onClick={() => setSidebarTab('archived')}
              className={cn(
                'flex-1 text-xs py-1.5 rounded-sm text-center transition-colors',
                sidebarTab === 'archived'
                  ? 'bg-[var(--color-surface)] shadow-sm text-[var(--color-text-main)]'
                  : 'text-[var(--color-text-sec)] hover:text-[var(--color-text-main)]',
              )}
            >
              Archived
            </button>
          </div>
        </div>

        {sidebarTab === 'archived' && (
          <div className="px-4 py-3 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-mut)]" />
              <input
                type="text"
                placeholder="Search by keyword or tag..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full h-8 pl-8 pr-3 text-xs bg-[var(--color-bg)] border border-[var(--color-border)] rounded-md focus:outline-none focus:border-[var(--color-primary)] text-[var(--color-text-main)] placeholder-[var(--color-text-mut)]"
              />
            </div>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-2 space-y-1 custom-scrollbar">
          {filteredConversations.map((conv) => (
            <div
              key={conv.id}
              onClick={() => handleSelectConversation(conv)}
              className="group relative px-3 py-2 rounded-md hover:bg-[var(--color-bg)] cursor-pointer transition-colors"
            >
              <div className="flex justify-between items-start mb-1">
                <span className="text-xs font-medium text-[var(--color-text-main)] truncate pr-2">
                  {conv.title || `Conversation ${conv.id.slice(0, 8)}`}
                </span>
                <span className="text-[10px] text-[var(--color-text-mut)] whitespace-nowrap">
                  {formatTime(new Date(conv.created_at))}
                </span>
              </div>
              {conv.tags && conv.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {conv.tags.map((tag) => (
                    <span key={tag} className="text-[9px] px-1.5 py-0.5 bg-[var(--color-primary)]/10 text-[var(--color-primary)] rounded">
                      #{tag}
                    </span>
                  ))}
                </div>
              )}

              {/* Hover Actions */}
              <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 flex items-center gap-1 bg-[var(--color-surface)] shadow-sm border border-[var(--color-border)] rounded-md p-0.5 transition-opacity">
                {sidebarTab === 'recent' && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      openArchiveModal(conv.id);
                    }}
                    className="p-1 text-[var(--color-text-sec)] hover:text-[var(--color-primary)] hover:bg-[var(--color-bg)] rounded"
                    title="Archive"
                  >
                    <Archive className="w-3.5 h-3.5" />
                  </button>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteConv(conv.id);
                  }}
                  className="p-1 text-[var(--color-text-sec)] hover:text-[var(--color-error)] hover:bg-[var(--color-bg)] rounded"
                  title="Delete"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
          {filteredConversations.length === 0 && (
            <div className="text-center text-xs text-[var(--color-text-mut)] mt-4">No conversations found.</div>
          )}
        </div>
      </div>

      {/* Center Chat Area */}
      <div className="flex-1 flex flex-col min-w-0 bg-[var(--color-bg)] relative">
        <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
          <AnimatePresence>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={cn('flex gap-4 max-w-[80%]', msg.role === 'user' ? 'ml-auto flex-row-reverse' : '')}
              >
                <div
                  className={cn(
                    'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm',
                    msg.role === 'user'
                      ? 'bg-[var(--color-bg)] border border-[var(--color-border)]'
                      : 'bg-[var(--color-primary)]/10',
                  )}
                >
                  {msg.role === 'user' ? (
                    <User className="w-4 h-4 text-[var(--color-text-sec)]" />
                  ) : (
                    <Bot className="w-4 h-4 text-[var(--color-primary)]" />
                  )}
                </div>

                  <div className="flex flex-col gap-1 min-w-[120px]">
                  <div
                    className={cn(
                      'px-4 py-3 text-sm shadow-sm',
                      msg.role === 'user'
                        ? 'bg-[var(--color-primary)] text-white rounded-l-md rounded-tr-xl rounded-br-md'
                        : 'bg-[var(--color-surface)] text-[var(--color-text-main)] rounded-r-md rounded-tl-xl rounded-bl-md border border-[var(--color-border)]',
                    )}
                  >
                    {msg.role === 'user' ? (
                      <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>
                    ) : (
                      <div className="markdown-body">
                        {msg.thinking && !msg.isStreaming && (
                          <ThinkingBlock
                            content={msg.thinking}
                            isExpanded={!!msg.isThinkingExpanded}
                            onToggle={() =>
                              setMessages((prev) =>
                                prev.map((m) =>
                                  m.id === msg.id ? { ...m, isThinkingExpanded: !m.isThinkingExpanded } : m,
                                ),
                              )
                            }
                          />
                        )}
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                        {msg.isStreaming && !msg.content && (
                          <span className="inline-block w-1.5 h-4 ml-1 bg-[var(--color-primary)] animate-pulse align-middle" />
                        )}
                      </div>
                    )}
                  </div>

                  {/* Time and Actions Row */}
                  <div className={cn('flex items-center mt-0.5', msg.role === 'user' ? 'justify-end' : 'justify-between ml-1')}>
                    {msg.role === 'model' && !msg.isStreaming && !feedbackSent[msg.id] && (
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleFeedback(msg.id, true)}
                          className="p-1 text-[var(--color-text-mut)] hover:text-[var(--color-primary)] hover:bg-[var(--color-primary)]/10 rounded-md transition-colors"
                          title="Helpful"
                        >
                          <ThumbsUp className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleFeedback(msg.id, false)}
                          className="p-1 text-[var(--color-text-mut)] hover:text-[var(--color-error)] hover:bg-[var(--color-error)]/10 rounded-md transition-colors"
                          title="Not helpful"
                        >
                          <ThumbsDown className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                    {msg.role === 'model' && feedbackSent[msg.id] && (
                      <span className="text-[10px] text-[var(--color-success)]">Thanks!</span>
                    )}
                    <div className="text-[10px] text-[var(--color-text-mut)]">{formatTime(msg.timestamp)}</div>
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {isTyping && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-4 max-w-[80%]">
              <div className="w-8 h-8 rounded-full bg-[var(--color-primary)]/10 flex items-center justify-center flex-shrink-0 shadow-sm">
                <Bot className="w-4 h-4 text-[var(--color-primary)]" />
              </div>
              <div className="px-4 py-3 bg-[var(--color-surface)] rounded-r-md rounded-tl-xl rounded-bl-md border border-[var(--color-border)] shadow-sm flex items-center gap-1">
                <span
                  className="w-1.5 h-1.5 bg-[var(--color-text-mut)] rounded-full animate-bounce"
                  style={{ animationDelay: '0ms' }}
                />
                <span
                  className="w-1.5 h-1.5 bg-[var(--color-text-mut)] rounded-full animate-bounce"
                  style={{ animationDelay: '150ms' }}
                />
                <span
                  className="w-1.5 h-1.5 bg-[var(--color-text-mut)] rounded-full animate-bounce"
                  style={{ animationDelay: '300ms' }}
                />
              </div>
            </motion.div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-[var(--color-surface)] border-t border-[var(--color-border)]">
          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Type your question..."
                disabled={isTyping}
                className="w-full min-h-[40px] max-h-[120px] p-2.5 border border-[var(--color-border)] rounded-md bg-[var(--color-surface)] text-[var(--color-text-main)] placeholder-[var(--color-text-mut)] focus:outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary)]/20 resize-none text-sm custom-scrollbar disabled:opacity-50"
                rows={1}
              />
            </div>

            <button
              onClick={handleSend}
              disabled={!input.trim() || isTyping}
              className="w-10 h-10 flex-shrink-0 bg-[var(--color-primary)] text-white rounded-md flex items-center justify-center hover:bg-[var(--color-primary-hover)] disabled:bg-[var(--color-text-mut)] disabled:cursor-not-allowed transition-colors"
            >
              <Send className="w-5 h-5 ml-0.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
