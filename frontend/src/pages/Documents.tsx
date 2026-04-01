import { useState, useRef, useEffect, useMemo } from 'react';
import { FileText, UploadCloud, RefreshCw, Folder, FolderOpen, Calendar, Trash2, ChevronDown, Loader2, CheckCircle2, XCircle, Search, ChevronLeft, ChevronRight, HardDrive, Database, Globe, Tag, Plus } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '../lib/utils';
import { listDocuments, uploadDocument, deleteDocument, listCategories, createCategory } from '../lib/api';
import type { DocumentResponse, Category } from '../types';

const computeTags = (fileType: string): string[] => {
  const ext = fileType.toLowerCase();
  if (ext === '.pdf') return ['document'];
  if (ext === '.doc' || ext === '.docx') return ['document'];
  if (ext === '.txt') return ['text'];
  if (['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'].includes(ext)) return ['image'];
  if (ext === '.csv' || ext === '.xlsx' || ext === '.xls') return ['spreadsheet'];
  if (ext === '.md') return ['markdown'];
  return ['auto-tagged'];
};

export default function Documents() {
  const [showUpload, setShowUpload] = useState(false);
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [uploadedDocIds, setUploadedDocIds] = useState<Set<string>>(new Set());
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [assigningDocId, setAssigningDocId] = useState<string | null>(null);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [newCategoryDesc, setNewCategoryDesc] = useState('');

  const enrichedDocuments = useMemo(() => {
    return documents.map(doc => ({
      ...doc,
      tags: doc.tags || computeTags(doc.file_type),
      source: doc.source || 'User Upload'
    }));
  }, [documents]);

  const allTags = useMemo(() => {
    const tagCounts = new Map<string, number>();
    enrichedDocuments.forEach(doc => {
      doc.tags.forEach(tag => {
        tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1);
      });
    });
    return Array.from(tagCounts.entries()).sort((a, b) => b[1] - a[1]);
  }, [enrichedDocuments]);

  const loadDocuments = async () => {
    setIsLoading(true);
    try {
      const docs = await listDocuments();
      setDocuments(docs);
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadCategories = async () => {
    try {
      const cats = await listCategories();
      setCategories(cats);
    } catch (error) {
      console.error('Failed to load categories:', error);
    }
  };

  useEffect(() => {
    loadDocuments();
    loadCategories();
  }, []);

  const itemsPerPage = 10;

  const filteredByTag = activeTag
    ? enrichedDocuments.filter(doc => doc.tags.includes(activeTag))
    : enrichedDocuments;

  const filteredDocuments = useMemo(() => {
    let result = filteredByTag;

    if (selectedCategory) {
      const category = categories.find(cat => cat.id === selectedCategory);
      if (category) {
        result = result.filter(doc =>
          doc.tags?.some(tag => tag === category.name)
        );
      }
    }

    return result.filter(doc =>
      doc.filename.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [filteredByTag, searchQuery, selectedCategory, categories]);

  const totalPages = Math.ceil(filteredDocuments.length / itemsPerPage);

  const paginatedDocuments = filteredDocuments.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, activeTag, selectedCategory]);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    try {
      const result = await uploadDocument(file);
      setUploadedDocIds(prev => new Set(prev).add(result.id));
      await loadDocuments();
      setShowUpload(false);
    } catch (error) {
      console.error('Failed to upload document:', error);
      alert(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (!file) return;

    setIsUploading(true);
    try {
      const result = await uploadDocument(file);
      setUploadedDocIds(prev => new Set(prev).add(result.id));
      await loadDocuments();
      setShowUpload(false);
    } catch (error) {
      console.error('Failed to upload document:', error);
      alert(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDelete = async (docId: string) => {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
      await deleteDocument(docId);
      setUploadedDocIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(docId);
        return newSet;
      });
      await loadDocuments();
    } catch (error) {
      console.error('Failed to delete document:', error);
      alert(error instanceof Error ? error.message : 'Delete failed');
    }
  };

  const toggleCategory = async (docId: string, categoryId: string, categoryName: string) => {
    const token = localStorage.getItem('token');
    const doc = documents.find(d => d.id === docId);
    const isAssigned = doc?.tags?.some(tag => tag === categoryName);

    try {
      if (isAssigned) {
        await fetch(`/api/documents/${docId}/categories/${categoryId}`, {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${token}` },
        });
      } else {
        await fetch(`/api/documents/${docId}/categories`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ category_id: categoryId }),
        });
      }
      await loadDocuments();
    } catch (error) {
      console.error('Failed to toggle category:', error);
      alert(error instanceof Error ? error.message : 'Operation failed');
    }
  };

  const handleCreateCategory = async () => {
    if (!newCategoryName.trim()) {
      alert('Category name is required');
      return;
    }

    try {
      await createCategory({ name: newCategoryName, description: newCategoryDesc });
      setNewCategoryName('');
      setNewCategoryDesc('');
      setShowCategoryModal(false);
      await loadCategories();
    } catch (error) {
      console.error('Failed to create category:', error);
      alert(error instanceof Error ? error.message : 'Failed to create category');
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getStatusInfo = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed':
      case 'success':
        return { type: 'success', icon: CheckCircle2 };
      case 'processing':
      case 'pending':
        return { type: 'info', icon: Loader2 };
      case 'failed':
      case 'error':
        return { type: 'error', icon: XCircle };
      default:
        return { type: 'info', icon: Loader2 };
    }
  };

  const getSourceIcon = (source: string) => {
    switch (source) {
      case 'User Upload':
        return <HardDrive className="w-3.5 h-3.5 text-[var(--color-info)]" />;
      case 'API Import':
        return <Database className="w-3.5 h-3.5 text-[var(--color-primary)]" />;
      case 'Website':
        return <Globe className="w-3.5 h-3.5 text-[var(--color-success)]" />;
      default:
        return <HardDrive className="w-3.5 h-3.5 text-[var(--color-info)]" />;
    }
  };

  return (
    <div className="flex-1 overflow-y-auto bg-[var(--color-bg)] p-8 custom-scrollbar">
      <div className="max-w-6xl mx-auto">

        <div className="flex justify-between items-center mb-8">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] flex items-center justify-center shadow-sm">
              <FileText className="w-5 h-5 text-[var(--color-text-sec)]" />
            </div>
            <h2 className="text-2xl font-semibold text-[var(--color-text-main)]">Document Management</h2>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={loadDocuments}
              disabled={isLoading}
              className="h-10 px-4 bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-main)] text-sm font-medium rounded-md hover:bg-[var(--color-bg)] transition-colors flex items-center gap-2 shadow-sm disabled:opacity-50"
            >
              <RefreshCw className={cn("w-4 h-4 text-[var(--color-text-sec)]", isLoading && "animate-spin")} />
              Refresh
            </button>
            <button
              onClick={() => setShowUpload(!showUpload)}
              className="h-10 px-4 bg-[var(--color-primary)] text-white text-sm font-medium rounded-md hover:bg-[var(--color-primary-hover)] transition-colors flex items-center gap-2 shadow-sm shadow-[var(--color-primary)]/20"
            >
              <UploadCloud className="w-4 h-4" />
              Upload Documents
              <ChevronDown className={cn("w-4 h-4 transition-transform", showUpload ? "rotate-180" : "")} />
            </button>
          </div>
        </div>

        <AnimatePresence>
          {showUpload && (
            <motion.div
              initial={{ height: 0, opacity: 0, marginBottom: 0 }}
              animate={{ height: 'auto', opacity: 1, marginBottom: 24 }}
              exit={{ height: 0, opacity: 0, marginBottom: 0 }}
              className="overflow-hidden"
            >
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onClick={handleUploadClick}
                className={cn(
                  "h-[180px] bg-[var(--color-surface)] border-2 border-dashed rounded-lg flex flex-col items-center justify-center transition-colors cursor-pointer group",
                  isUploading ? "border-[var(--color-border)] cursor-not-allowed opacity-50" : "border-[var(--color-border)] hover:border-[var(--color-primary)] hover:bg-[var(--color-primary)]/5"
                )}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  onChange={handleFileSelect}
                  disabled={isUploading}
                  className="hidden"
                />
                {isUploading ? (
                  <>
                    <Loader2 className="w-12 h-12 text-[var(--color-primary)] animate-spin mb-4" />
                    <p className="text-base text-[var(--color-text-main)] font-medium">Uploading document...</p>
                  </>
                ) : (
                  <>
                    <UploadCloud className="w-12 h-12 text-[var(--color-text-mut)] group-hover:text-[var(--color-primary)] transition-colors mb-4" />
                    <p className="text-base text-[var(--color-text-main)] font-medium">Drag files here</p>
                    <p className="text-sm text-[var(--color-text-sec)] mt-1">or click to browse from your computer</p>
                  </>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex items-center gap-4 mb-6 flex-wrap">
          <div className="relative w-full md:w-72">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-mut)]" />
            <input
              type="text"
              placeholder="Search documents by name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full h-10 pl-9 pr-4 text-sm bg-[var(--color-surface)] border border-[var(--color-border)] rounded-md focus:outline-none focus:border-[var(--color-primary)] text-[var(--color-text-main)] placeholder-[var(--color-text-mut)] shadow-sm"
            />
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <FolderOpen className="w-4 h-4 text-[var(--color-text-sec)]" />
            <button
              onClick={() => setSelectedCategory(null)}
              className={cn(
                "h-7 px-3 text-xs font-medium rounded-full cursor-pointer transition-colors",
                selectedCategory === null
                  ? "bg-[var(--color-primary)] text-white"
                  : "bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-sec)] hover:bg-[var(--color-bg)]"
              )}
            >
              All Categories ({enrichedDocuments.length})
            </button>
            {categories.map(cat => {
              const docCount = enrichedDocuments.filter(doc =>
                doc.tags?.some(tag => tag === cat.name)
              ).length;
              return (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(selectedCategory === cat.id ? null : cat.id)}
                  className={cn(
                    "h-7 px-3 text-xs font-medium rounded-full cursor-pointer transition-colors",
                    selectedCategory === cat.id
                      ? "bg-[var(--color-primary)] text-white"
                      : "bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-sec)] hover:bg-[var(--color-bg)]"
                  )}
                >
                  {cat.name} ({docCount})
                </button>
              );
            })}
            <button
              onClick={() => setShowCategoryModal(true)}
              className="h-7 w-7 flex items-center justify-center rounded-full bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-sec)] hover:bg-[var(--color-bg)] hover:text-[var(--color-primary)] transition-colors"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <Tag className="w-4 h-4 text-[var(--color-text-sec)]" />
            <button
              onClick={() => setActiveTag(null)}
              className={cn(
                "h-7 px-3 text-xs font-medium rounded-full cursor-pointer transition-colors",
                activeTag === null
                  ? "bg-[var(--color-primary)] text-white"
                  : "bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-sec)] hover:bg-[var(--color-bg)]"
              )}
            >
              All ({enrichedDocuments.length})
            </button>
            {allTags.map(([tagName, count]) => (
              <button
                key={tagName}
                onClick={() => setActiveTag(activeTag === tagName ? null : tagName)}
                className={cn(
                  "h-7 px-3 text-xs font-medium rounded-full cursor-pointer transition-colors",
                  activeTag === tagName
                    ? "bg-[var(--color-primary)] text-white"
                    : "bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-sec)] hover:bg-[var(--color-bg)]"
                )}
              >
                {tagName} ({count})
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 text-[var(--color-primary)] animate-spin" />
          </div>
        ) : (
           <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {paginatedDocuments.map((doc) => {
              const statusInfo = getStatusInfo(doc.status);
              const StatusIcon = statusInfo.icon;
              const isNew = uploadedDocIds.has(doc.id);
              const displayTags = isNew ? [...doc.tags, 'new'] : doc.tags;

              return (
                <motion.div
                  key={doc.id}
                  whileHover={{ y: -2 }}
                  className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-5 shadow-sm hover:shadow-md transition-all duration-200 hover:border-[var(--color-primary)]/30"
                >
                  <div className="flex justify-between items-start mb-3">
                    <h3 className="text-sm font-medium text-[var(--color-text-main)] truncate max-w-[200px]" title={doc.filename}>
                      {doc.filename}
                    </h3>
                    <span className={cn(
                      "text-[11px] px-2 py-0.5 rounded-full flex-shrink-0 flex items-center gap-1 font-medium",
                      statusInfo.type === 'success' ? "bg-[var(--color-success)]/15 text-[var(--color-success)]" :
                      statusInfo.type === 'info' ? "bg-[var(--color-info)]/15 text-[var(--color-info)]" :
                      "bg-[var(--color-error)]/15 text-[var(--color-error)]"
                    )}>
                      {statusInfo.type === 'info' && <StatusIcon className="w-3 h-3 animate-spin" />}
                      {statusInfo.type !== 'info' && <StatusIcon className="w-3 h-3" />}
                      {doc.status}
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-1.5 mb-4">
                    {displayTags.filter(tag => categories.some(cat => cat.name === tag)).map(catTag => (
                      <span
                        key={catTag}
                        className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-[var(--color-info)]/15 text-[var(--color-info)]"
                      >
                        {catTag}
                      </span>
                    ))}
                    {displayTags.filter(tag => !categories.some(cat => cat.name === tag)).map(tag => (
                      <span
                        key={tag}
                        className={cn(
                          "text-[10px] px-1.5 py-0.5 rounded font-medium",
                          tag === 'new'
                            ? "bg-[var(--color-success)]/15 text-[var(--color-success)]"
                            : "bg-[var(--color-primary)]/10 text-[var(--color-primary)]"
                        )}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>

                  <div className="flex flex-wrap gap-4 mb-4">
                    <div className="flex items-center gap-1.5 text-xs text-[var(--color-text-sec)]">
                      <Folder className="w-3.5 h-3.5 text-[var(--color-text-mut)]" />
                      {formatFileSize(doc.file_size)}
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-[var(--color-text-sec)]">
                      <FileText className="w-3.5 h-3.5 text-[var(--color-text-mut)]" />
                      {doc.chunks_count} chunks
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-[var(--color-text-sec)]">
                      <Calendar className="w-3.5 h-3.5 text-[var(--color-text-mut)]" />
                      {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : '-'}
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-[var(--color-text-sec)]">
                      {getSourceIcon(doc.source || 'User Upload')}
                      {doc.source || 'User Upload'}
                    </div>
                  </div>

                  <div className="flex justify-between items-center pt-3 border-t border-[var(--color-border)]">
                    <div className="relative">
                      <button
                        onClick={() => setAssigningDocId(assigningDocId === doc.id ? null : doc.id)}
                        className="h-7 px-3 bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-sec)] text-xs font-medium rounded hover:bg-[var(--color-bg)] hover:text-[var(--color-text-main)] transition-colors flex items-center gap-1.5"
                      >
                        <FolderOpen className="w-3.5 h-3.5" />
                        Category
                      </button>
                      <AnimatePresence>
                        {assigningDocId === doc.id && (
                          <motion.div
                            initial={{ opacity: 0, y: -5 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -5 }}
                            className="absolute top-full left-0 mt-2 w-48 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-lg z-10"
                          >
                            {categories.length === 0 ? (
                              <div className="p-3 text-xs text-[var(--color-text-sec)]">No categories</div>
                            ) : (
                              categories.map(cat => {
                                const isAssigned = doc.tags?.some(tag => tag === cat.name);
                                return (
                                  <button
                                    key={cat.id}
                                    onClick={() => toggleCategory(doc.id, cat.id, cat.name)}
                                    className="w-full px-3 py-2 text-left text-xs flex items-center justify-between hover:bg-[var(--color-bg)] transition-colors first:rounded-t-lg last:rounded-b-lg"
                                  >
                                    <span className={cn(
                                      "text-[var(--color-text-main)]",
                                      isAssigned && "font-medium text-[var(--color-primary)]"
                                    )}>
                                      {cat.name}
                                    </span>
                                    {isAssigned && <CheckCircle2 className="w-3 h-3 text-[var(--color-primary)]" />}
                                  </button>
                                );
                              })
                            )}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                    <button
                      onClick={() => handleDelete(doc.id)}
                      className="h-7 px-3 bg-[var(--color-error)]/10 text-[var(--color-error)] text-xs font-medium rounded hover:bg-[var(--color-error)]/20 transition-colors flex items-center gap-1.5"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      Delete
                    </button>
                  </div>
                </motion.div>
              );
            })}
           </div>
         )}

         {totalPages > 1 && !isLoading && (
           <div className="flex items-center justify-between bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg px-4 py-3 shadow-sm">
             <span className="text-sm text-[var(--color-text-sec)]">
               Showing <span className="font-medium text-[var(--color-text-main)]">{(currentPage - 1) * itemsPerPage + 1}</span> to <span className="font-medium text-[var(--color-text-main)]">{Math.min(currentPage * itemsPerPage, filteredDocuments.length)}</span> of <span className="font-medium text-[var(--color-text-main)]">{filteredDocuments.length}</span> results
             </span>
             <div className="flex items-center gap-2">
               <button
                 onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                 disabled={currentPage === 1}
                 className="p-1.5 rounded-md border border-[var(--color-border)] text-[var(--color-text-sec)] hover:bg-[var(--color-bg)] hover:text-[var(--color-text-main)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
               >
                 <ChevronLeft className="w-4 h-4" />
               </button>
               <div className="flex items-center gap-1">
                 {Array.from({ length: totalPages }).map((_, i) => (
                   <button
                     key={i}
                     onClick={() => setCurrentPage(i + 1)}
                     className={cn(
                       "w-8 h-8 rounded-md text-sm font-medium transition-colors",
                       currentPage === i + 1
                         ? "bg-[var(--color-primary)] text-white"
                         : "text-[var(--color-text-sec)] hover:bg-[var(--color-bg)] hover:text-[var(--color-text-main)]"
                     )}
                   >
                     {i + 1}
                   </button>
                 ))}
               </div>
               <button
                 onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                 disabled={currentPage === totalPages}
                 className="p-1.5 rounded-md border border-[var(--color-border)] text-[var(--color-text-sec)] hover:bg-[var(--color-bg)] hover:text-[var(--color-text-main)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
               >
                 <ChevronRight className="w-4 h-4" />
               </button>
             </div>
           </div>
         )}

          {!isLoading && filteredDocuments.length === 0 && (
            <div className="text-center py-20">
             <FileText className="w-16 h-16 text-[var(--color-text-mut)] mx-auto mb-4" />
             <p className="text-sm text-[var(--color-text-sec)]">No documents uploaded yet</p>
             <p className="text-xs text-[var(--color-text-mut)] mt-1">Click "Upload Documents" to get started</p>
           </div>
         )}

         <AnimatePresence>
           {showCategoryModal && (
             <motion.div
               initial={{ opacity: 0 }}
               animate={{ opacity: 1 }}
               exit={{ opacity: 0 }}
               className="fixed inset-0 bg-[var(--color-text-main)]/20 backdrop-blur-sm flex items-center justify-center z-50"
               onClick={() => setShowCategoryModal(false)}
             >
               <motion.div
                 initial={{ opacity: 0, scale: 0.95 }}
                 animate={{ opacity: 1, scale: 1 }}
                 exit={{ opacity: 0, scale: 0.95 }}
                 onClick={(e) => e.stopPropagation()}
                 className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-xl p-6 w-full max-w-md"
               >
                 <h3 className="text-lg font-semibold text-[var(--color-text-main)] mb-4">Create New Category</h3>
                 <div className="space-y-4">
                   <div>
                     <label className="block text-sm font-medium text-[var(--color-text-main)] mb-2">Name <span className="text-[var(--color-error)]">*</span></label>
                     <input
                       type="text"
                       value={newCategoryName}
                       onChange={(e) => setNewCategoryName(e.target.value)}
                       className="w-full h-10 px-4 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-md focus:outline-none focus:border-[var(--color-primary)] text-[var(--color-text-main)] placeholder-[var(--color-text-mut)]"
                       placeholder="Enter category name"
                     />
                   </div>
                   <div>
                     <label className="block text-sm font-medium text-[var(--color-text-main)] mb-2">Description</label>
                     <textarea
                       value={newCategoryDesc}
                       onChange={(e) => setNewCategoryDesc(e.target.value)}
                       className="w-full h-24 px-4 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-md focus:outline-none focus:border-[var(--color-primary)] text-[var(--color-text-main)] placeholder-[var(--color-text-mut)] resize-none"
                       placeholder="Enter category description (optional)"
                     />
                   </div>
                 </div>
                 <div className="flex justify-end gap-3 mt-6">
                   <button
                     onClick={() => {
                       setShowCategoryModal(false);
                       setNewCategoryName('');
                       setNewCategoryDesc('');
                     }}
                     className="h-10 px-4 bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-main)] text-sm font-medium rounded-md hover:bg-[var(--color-bg)] transition-colors"
                   >
                     Cancel
                   </button>
                   <button
                     onClick={handleCreateCategory}
                     disabled={!newCategoryName.trim()}
                     className="h-10 px-4 bg-[var(--color-primary)] text-white text-sm font-medium rounded-md hover:bg-[var(--color-primary-hover)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                   >
                     Create Category
                   </button>
                 </div>
               </motion.div>
             </motion.div>
           )}
         </AnimatePresence>
       </div>
     </div>
   );
 }
