import { useState, useEffect } from 'react';
import { Users, Shield, Activity, Cpu, Edit2, Trash2, Check, X, Loader2, Plus, Key } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '../lib/utils';
import {
  listModelConfigs, createModelConfig, updateModelConfig, deleteModelConfig, testModelConnection,
  listUsers, createUser, updateUser, deleteUser, resetPassword,
  getAuditLogs, listRoles,
} from '../lib/api';
import type {
  ModelConfig, CreateModelConfig, UpdateModelConfig,
  User, CreateUser, UpdateUser,
  AuditLog,
  Role,
} from '../types';

type Tab = 'users' | 'roles' | 'audit' | 'models';

export default function Admin() {
  const [activeTab, setActiveTab] = useState<Tab>('users');

  const tabs = [
    { id: 'users', label: 'User Management', icon: Users },
    { id: 'roles', label: 'Role Permissions', icon: Shield },
    { id: 'models', label: 'Model Management', icon: Cpu },
  ];

  return (
    <div className="flex-1 flex flex-col bg-[var(--color-bg)] overflow-hidden">
      <div className="h-12 bg-[var(--color-surface)] border-b border-[var(--color-border)] flex px-8 flex-shrink-0">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as Tab)}
            className={cn(
              "h-full px-6 flex items-center gap-2 text-sm transition-colors border-b-2",
              activeTab === tab.id 
                ? "border-[var(--color-primary)] text-[var(--color-text-main)] font-semibold" 
                : "border-transparent text-[var(--color-text-sec)] hover:text-[var(--color-text-main)]"
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
        <div className="max-w-6xl mx-auto">
          {activeTab === 'users' && <UserManagement />}
          {activeTab === 'roles' && <RolePermissions />}
          {activeTab === 'audit' && <AuditLog />}
          {activeTab === 'models' && <ModelManagement />}
        </div>
      </div>
    </div>
  );
}

function UserManagement() {
  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showResetModal, setShowResetModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [resetSuccess, setResetSuccess] = useState(false);
  const [tempPassword, setTempPassword] = useState('');

  const [addForm, setAddForm] = useState({ username: '', password: '', role: 'user' });
  const [editForm, setEditForm] = useState({ username: '', role: 'user' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [roles, setRoles] = useState<Role[]>([]);

  const inputCls = "w-full h-9 px-3 text-sm border border-[var(--color-border)] rounded-md bg-[var(--color-bg)] text-[var(--color-text-main)] placeholder-[var(--color-text-mut)] focus:outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary)]/20";

  const loadUsers = async () => {
    setIsLoading(true);
    try {
      const data = await listUsers();
      setUsers(data);
    } catch (error) {
      console.error('Failed to load users:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadRoles = async () => {
    try {
      const data = await listRoles();
      setRoles(data);
    } catch (error) {
      console.error('Failed to load roles:', error);
    }
  };

  useEffect(() => {
    loadUsers();
    loadRoles();
  }, []);

  const handleAddUser = async () => {
    if (!addForm.username.trim() || !addForm.password.trim()) return;
    setIsSubmitting(true);
    try {
      const createData: CreateUser = {
        username: addForm.username.trim(),
        password: addForm.password.trim(),
        role: addForm.role,
      };
      await createUser(createData);
      setShowAddModal(false);
      setAddForm({ username: '', password: '', role: 'user' });
      await loadUsers();
    } catch (error) {
      console.error('Failed to create user:', error);
      alert(error instanceof Error ? error.message : 'Failed to create user');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResetPassword = async () => {
    if (!selectedUser) return;
    setIsSubmitting(true);
    try {
      const result = await resetPassword(selectedUser.id);
      setTempPassword(result.temp_password);
      setResetSuccess(true);
    } catch (error) {
      console.error('Failed to reset password:', error);
      alert(error instanceof Error ? error.message : 'Failed to reset password');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEditUser = async () => {
    if (!selectedUser || !editForm.username.trim()) return;
    setIsSubmitting(true);
    try {
      const updateData: UpdateUser = {
        username: editForm.username.trim(),
        role: editForm.role,
      };
      await updateUser(selectedUser.id, updateData);
      setShowEditModal(false);
      setSelectedUser(null);
      await loadUsers();
    } catch (error) {
      console.error('Failed to update user:', error);
      alert(error instanceof Error ? error.message : 'Failed to update user');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteUser = async (userId: string) => {
    if (window.confirm('Are you sure you want to delete this user?')) {
      try {
        await deleteUser(userId);
        await loadUsers();
      } catch (error) {
        console.error('Failed to delete user:', error);
        alert(error instanceof Error ? error.message : 'Failed to delete user');
      }
    }
  };

  const openResetModal = (user: User) => {
    setSelectedUser(user);
    setResetSuccess(false);
    setTempPassword('');
    setShowResetModal(true);
  };

  const openEditModal = (user: User) => {
    setSelectedUser(user);
    setEditForm({ username: user.username, role: user.role });
    setShowEditModal(true);
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-[var(--color-text-main)]">User List</h3>
        <button
          onClick={() => setShowAddModal(true)}
          className="h-9 px-4 bg-[var(--color-primary)] text-white text-sm font-medium rounded-md hover:bg-[var(--color-primary-hover)] transition-colors flex items-center gap-2 shadow-sm"
        >
          <Plus className="w-4 h-4" /> Add User
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-[var(--color-primary)] animate-spin" />
        </div>
      ) : (
      <>
      <AnimatePresence>
        {showAddModal && (
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
              className="bg-[var(--color-surface)] rounded-lg shadow-xl w-full max-w-lg p-6 border border-[var(--color-border)]"
            >
               <h3 className="text-lg font-semibold text-[var(--color-text-main)] mb-5">Add New User</h3>
               <div className="space-y-4">
                 <div>
                   <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Username *</label>
                   <input
                     type="text"
                     value={addForm.username}
                     onChange={e => setAddForm({ ...addForm, username: e.target.value })}
                     placeholder="Enter username"
                     className={inputCls}
                   />
                 </div>
                 <div>
                   <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Password *</label>
                   <input
                     type="password"
                     value={addForm.password}
                     onChange={e => setAddForm({ ...addForm, password: e.target.value })}
                     placeholder="Enter password"
                     className={inputCls}
                   />
                 </div>
                 <div>
                   <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Role *</label>
                   <select
                     value={addForm.role}
                     onChange={e => setAddForm({ ...addForm, role: e.target.value })}
                     className={inputCls}
                   >
                     {roles.map(role => (
                       <option key={role.name} value={role.name}>{role.display_name}</option>
                     ))}
                   </select>
                 </div>
               </div>
              <div className="flex justify-end gap-2 mt-6">
                <button
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 text-sm text-[var(--color-text-sec)] hover:bg-[var(--color-bg)] rounded-md transition-colors"
                >
                  Cancel
                </button>
                 <button
                   onClick={handleAddUser}
                   disabled={!addForm.username.trim() || !addForm.password.trim() || isSubmitting}
                   className="px-4 py-2 text-sm bg-[var(--color-primary)] text-white rounded-md hover:bg-[var(--color-primary-hover)] transition-colors disabled:opacity-50 flex items-center gap-2"
                 >
                   {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
                   {isSubmitting ? 'Adding...' : 'Add User'}
                 </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showResetModal && selectedUser && (
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
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold text-[var(--color-text-main)]">Reset Password</h3>
                <button onClick={() => setShowResetModal(false)} className="text-[var(--color-text-mut)] hover:text-[var(--color-text-main)]">
                  <X className="w-4 h-4" />
                </button>
              </div>
              {!resetSuccess ? (
                <>
                  <p className="text-sm text-[var(--color-text-sec)] mb-6">
                    Are you sure you want to reset the password for user <strong className="text-[var(--color-text-main)]">{selectedUser.username}</strong>? A temporary password will be generated.
                  </p>
                  <div className="flex justify-end gap-2">
                    <button onClick={() => setShowResetModal(false)} className="px-4 py-2 text-sm text-[var(--color-text-sec)] hover:bg-[var(--color-bg)] rounded-md transition-colors">Cancel</button>
                    <button onClick={handleResetPassword} disabled={isSubmitting} className="px-4 py-2 text-sm bg-[var(--color-primary)] text-white rounded-md hover:bg-[var(--color-primary-hover)] transition-colors disabled:opacity-50 flex items-center gap-2">
                      {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
                      {isSubmitting ? 'Resetting...' : 'Confirm Reset'}
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div className="p-4 bg-[var(--color-success)]/10 border border-[var(--color-success)]/20 rounded-md mb-6">
                    <p className="text-sm text-[var(--color-success)] flex items-center gap-2 font-medium mb-3">
                      <Check className="w-4 h-4" /> Password Reset Successful
                    </p>
                    <p className="text-xs text-[var(--color-text-sec)] mb-2">
                      New temporary password for <strong className="text-[var(--color-text-main)]">{selectedUser.username}</strong>:
                    </p>
                    <div className="p-2 bg-[var(--color-bg)] rounded border border-[var(--color-border)] font-mono text-center text-[var(--color-text-main)] tracking-wider select-all">
                      {tempPassword}
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <button onClick={() => setShowResetModal(false)} className="px-4 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text-main)] rounded-md hover:bg-[var(--color-surface)] transition-colors">Close</button>
                  </div>
                </>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showEditModal && selectedUser && (
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
              className="bg-[var(--color-surface)] rounded-lg shadow-xl w-full max-w-lg p-6 border border-[var(--color-border)]"
            >
              <h3 className="text-lg font-semibold text-[var(--color-text-main)] mb-5">Edit User</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Username *</label>
                  <input
                    type="text"
                    value={editForm.username}
                    onChange={e => setEditForm({ ...editForm, username: e.target.value })}
                    className={inputCls}
                  />
                </div>
                 <div>
                   <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Role *</label>
                   <select
                     value={editForm.role}
                     onChange={e => setEditForm({ ...editForm, role: e.target.value })}
                     className={inputCls}
                   >
                     {roles.map(role => (
                       <option key={role.name} value={role.name}>{role.display_name}</option>
                     ))}
                   </select>
                 </div>
              </div>
              <div className="flex justify-end gap-2 mt-6">
                <button
                  onClick={() => setShowEditModal(false)}
                  className="px-4 py-2 text-sm text-[var(--color-text-sec)] hover:bg-[var(--color-bg)] rounded-md transition-colors"
                >
                  Cancel
                </button>
                 <button
                   onClick={handleEditUser}
                   disabled={!editForm.username.trim() || isSubmitting}
                   className="px-4 py-2 text-sm bg-[var(--color-primary)] text-white rounded-md hover:bg-[var(--color-primary-hover)] transition-colors disabled:opacity-50 flex items-center gap-2"
                 >
                   {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
                   {isSubmitting ? 'Saving...' : 'Save'}
                 </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-sm overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-[var(--color-bg)] border-b border-[var(--color-border)] text-xs text-[var(--color-text-sec)] font-semibold uppercase tracking-wider">
              <th className="px-6 py-3 w-[20%]">Username</th>
              <th className="px-6 py-3 w-[15%]">User ID</th>
              <th className="px-6 py-3 w-[15%]">Role</th>
              <th className="px-6 py-3 w-[15%]">Status</th>
              <th className="px-6 py-3 w-[35%]">Actions</th>
            </tr>
          </thead>
          <tbody className="text-sm text-[var(--color-text-main)]">
            {users.map((user) => (
              <tr key={user.id} className="border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-bg)]/50 transition-colors">
                <td className="px-6 py-4 font-medium">{user.username}</td>
                <td className="px-6 py-4 text-[var(--color-text-sec)]">{user.id}</td>
                <td className="px-6 py-4">
                  <span className={cn(
                    "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
                    user.role === 'admin' ? "bg-[var(--color-primary)]/10 text-[var(--color-primary)]" : "bg-[var(--color-info)]/10 text-[var(--color-info)]"
                  )}>
                    {roles.find(r => r.name === user.role)?.display_name || user.role}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <span className={cn(
                    "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
                    user.is_active ? "bg-[var(--color-success)]/10 text-[var(--color-success)]" : "bg-[var(--color-error)]/10 text-[var(--color-error)]"
                  )}>
                    {user.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-6 py-4 flex gap-4">
                  <button
                    onClick={() => openResetModal(user)}
                    className="text-[var(--color-info)] hover:text-blue-600 font-medium flex items-center gap-1"
                    title="Reset Password"
                  >
                    <Key className="w-3.5 h-3.5" /> Reset
                  </button>
                  <button
                    onClick={() => openEditModal(user)}
                    className="text-[var(--color-primary)] hover:text-[var(--color-primary-hover)] font-medium flex items-center gap-1"
                    title="Edit"
                  >
                    <Edit2 className="w-3.5 h-3.5" /> Edit
                  </button>
                  <button
                    onClick={() => handleDeleteUser(user.id)}
                    className="text-[var(--color-error)] hover:text-red-700 font-medium flex items-center gap-1"
                    title="Delete"
                  >
                    <Trash2 className="w-3.5 h-3.5" /> Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      </>
      )}
    </motion.div>
  );
}

function RolePermissions() {
  const roles = [
    { name: 'System Admin', level: 'Level 1', perms: [true, true, true, true, true] },
    { name: 'Document Admin', level: 'Level 2', perms: [false, false, true, true, true] },
    { name: 'Standard User', level: 'Level 3', perms: [false, false, false, true, false] },
  ];
  const permLabels = ['User management', 'Role configuration', 'Document upload', 'Document query', 'Audit logs'];

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {roles.map((role, i) => (
          <div key={i} className="p-5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-sm hover:shadow-md transition-shadow">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-[var(--color-text-main)]">{role.name}</h3>
              <span className="text-xs px-2 py-1 bg-[var(--color-primary)]/15 text-[var(--color-primary)] rounded-full font-medium">
                {role.level}
              </span>
            </div>
            <p className="text-sm text-[var(--color-text-sec)] mb-3 font-medium">Permissions:</p>
            <ul className="space-y-2">
              {role.perms.map((hasPerm, j) => (
                <li key={j} className="flex items-center gap-2 text-sm text-[var(--color-text-main)]">
                  {hasPerm ? (
                    <Check className="w-4 h-4 text-[var(--color-success)]" />
                  ) : (
                    <X className="w-4 h-4 text-[var(--color-error)]" />
                  )}
                  <span className={hasPerm ? "" : "text-[var(--color-text-mut)] line-through"}>{permLabels[j]}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

function AuditLog() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const pageSize = 20;

  const formatRelativeTime = (dateString: string) => {
    const now = new Date();
    const date = new Date(dateString);
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} mins ago`;
    if (diffHours < 24) return `${diffHours} hours ago`;
    if (diffDays < 7) return `${diffDays} days ago`;
    return date.toLocaleDateString();
  };

  const loadLogs = async (pageNum: number) => {
    setIsLoading(true);
    try {
      const data = await getAuditLogs(pageNum, pageSize);
      setLogs(data.items || []);
      setTotalPages(data.total_pages || 1);
    } catch (error) {
      console.error('Failed to load audit logs:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadLogs(page);
  }, [page]);

  const handlePrevPage = () => {
    if (page > 1) setPage(page - 1);
  };

  const handleNextPage = () => {
    if (page < totalPages) setPage(page + 1);
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-[var(--color-text-main)]">Audit Log</h3>
        <div className="flex items-center gap-2 text-sm text-[var(--color-text-sec)]">
          <button
            onClick={handlePrevPage}
            disabled={page === 1 || isLoading}
            className="px-3 py-1 border border-[var(--color-border)] rounded hover:bg-[var(--color-bg)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Previous
          </button>
          <span className="text-xs">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={handleNextPage}
            disabled={page >= totalPages || isLoading}
            className="px-3 py-1 border border-[var(--color-border)] rounded hover:bg-[var(--color-bg)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Next
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-[var(--color-primary)] animate-spin" />
        </div>
      ) : (
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-sm overflow-hidden max-h-[calc(100vh-240px)] overflow-y-auto custom-scrollbar">
          {logs.length === 0 ? (
            <div className="p-8 text-center text-[var(--color-text-sec)]">
              No audit logs found.
            </div>
          ) : (
            logs.map((log) => (
              <div key={log.id} className="p-4 border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-bg)]/50 transition-colors">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm font-semibold text-[var(--color-text-main)]">{log.action}</span>
                  <span className="text-xs text-[var(--color-text-mut)]">{formatRelativeTime(log.created_at)}</span>
                </div>
                <div className="flex gap-4 text-xs">
                  <span className="text-[var(--color-text-mut)]">User: <span className="text-[var(--color-text-sec)] font-medium">{log.username || 'N/A'}</span></span>
                  <span className="text-[var(--color-text-mut)]">IP: <span className="text-[var(--color-text-sec)] font-medium">{log.ip_address || 'N/A'}</span></span>
                  <span className="text-[var(--color-text-sec)] truncate max-w-[300px]">{log.details || ''}</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </motion.div>
  );
}

function ModelManagement() {
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [testing, setTesting] = useState<Record<string, boolean>>({});
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [formError, setFormError] = useState('');
  const [selectedModel, setSelectedModel] = useState<ModelConfig | null>(null);

  const [form, setForm] = useState<CreateModelConfig>({
    name: '',
    provider: '',
    model_id: '',
    api_base: '',
    api_key: '',
    model_type: 'llm',
    max_tokens: 4096,
    is_default: false,
    description: '',
  });

  const [editForm, setEditForm] = useState<UpdateModelConfig>({});

  const loadModels = async () => {
    setIsLoading(true);
    try {
      const modelConfigs = await listModelConfigs();
      setModels(modelConfigs);
    } catch (error) {
      console.error('Failed to load models:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useState(() => {
    loadModels();
  });

  const handleTest = async (modelId: string) => {
    setTesting(prev => ({ ...prev, [modelId]: true }));
    try {
      const result = await testModelConnection(modelId);
      if (result.success) {
        alert(`Connection successful!\nResponse time: ${result.response_time}ms`);
      } else {
        alert(`Connection failed: ${result.message}`);
      }
    } catch (error) {
      console.error('Failed to test connection:', error);
      alert(error instanceof Error ? error.message : 'Test failed');
    } finally {
      setTesting(prev => ({ ...prev, [modelId]: false }));
    }
  };

  const handleDelete = async (modelId: string) => {
    if (!confirm('Are you sure you want to delete this model configuration?')) return;

    try {
      await deleteModelConfig(modelId);
      await loadModels();
    } catch (error) {
      console.error('Failed to delete model:', error);
      alert(error instanceof Error ? error.message : 'Delete failed');
    }
  };

  const handleSetDefault = async (modelId: string) => {
    try {
      await updateModelConfig(modelId, { is_default: true });
      await loadModels();
    } catch (error) {
      console.error('Failed to set default model:', error);
      alert(error instanceof Error ? error.message : 'Operation failed');
    }
  };

  const openAddModal = () => {
    setForm({
      name: '',
      provider: '',
      model_id: '',
      api_base: '',
      api_key: '',
      model_type: 'llm',
      max_tokens: 4096,
      is_default: false,
      description: '',
    });
    setFormError('');
    setShowAddModal(true);
  };

  const openEditModal = (model: ModelConfig) => {
    setSelectedModel(model);
    setEditForm({
      name: model.name,
      provider: model.provider,
      model_id: model.model_id,
      api_base: model.api_base,
      model_type: model.model_type,
      max_tokens: model.max_tokens,
      is_default: model.is_default,
      is_active: model.is_active,
      description: model.description || '',
    });
    setFormError('');
    setShowEditModal(true);
  };

  const handleEdit = async () => {
    if (!selectedModel) return;
    if (!editForm.name || !editForm.provider || !editForm.model_id) {
      setFormError('Name, Provider, and Model ID are required.');
      return;
    }

    setIsUpdating(true);
    setFormError('');
    try {
      await updateModelConfig(selectedModel.id, editForm);
      await loadModels();
      setShowEditModal(false);
      setSelectedModel(null);
    } catch (error) {
      console.error('Failed to update model:', error);
      setFormError(error instanceof Error ? error.message : 'Failed to update model');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleCreate = async () => {
    if (!form.name || !form.provider || !form.model_id) {
      setFormError('Name, Provider, and Model ID are required.');
      return;
    }

    setIsCreating(true);
    setFormError('');
    try {
      await createModelConfig(form);
      await loadModels();
      setShowAddModal(false);
    } catch (error) {
      console.error('Failed to create model:', error);
      setFormError(error instanceof Error ? error.message : 'Failed to create model');
    } finally {
      setIsCreating(false);
    }
  };

  const updateForm = (field: keyof CreateModelConfig, value: string | number | boolean) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  const inputCls = "w-full h-9 px-3 text-sm border border-[var(--color-border)] rounded-md bg-[var(--color-bg)] text-[var(--color-text-main)] placeholder-[var(--color-text-mut)] focus:outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary)]/20";

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-[var(--color-text-main)]">Model Configuration</h3>
        <button
          onClick={openAddModal}
          className="h-9 px-4 bg-[var(--color-primary)] text-white text-sm font-medium rounded-md hover:bg-[var(--color-primary-hover)] transition-colors flex items-center gap-2 shadow-sm"
        >
          <Plus className="w-4 h-4" /> Add Model
        </button>
      </div>

      {/* Add Model Modal */}
      <AnimatePresence>
        {showAddModal && (
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
              className="bg-[var(--color-surface)] rounded-lg shadow-xl w-full max-w-lg p-6 border border-[var(--color-border)]"
            >
              <h3 className="text-lg font-semibold text-[var(--color-text-main)] mb-5">Add New Model</h3>

              {formError && (
                <div className="mb-4 p-2 bg-[var(--color-error)]/10 text-[var(--color-error)] text-sm rounded-md text-center">
                  {formError}
                </div>
              )}

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Name *</label>
                    <input
                      value={form.name}
                      onChange={e => updateForm('name', e.target.value)}
                      placeholder="e.g. GLM-4"
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Provider *</label>
                    <input
                      value={form.provider}
                      onChange={e => updateForm('provider', e.target.value)}
                      placeholder="e.g. zhipu, openai"
                      className={inputCls}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Model ID *</label>
                    <input
                      value={form.model_id}
                      onChange={e => updateForm('model_id', e.target.value)}
                      placeholder="e.g. glm-4"
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Type</label>
                    <select
                      value={form.model_type}
                      onChange={e => updateForm('model_type', e.target.value)}
                      className={inputCls}
                    >
                      <option value="llm">LLM</option>
                      <option value="embedding">Embedding</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">API Base</label>
                  <input
                    value={form.api_base || ''}
                    onChange={e => updateForm('api_base', e.target.value)}
                    placeholder="https://api.example.com/v1"
                    className={inputCls}
                  />
                </div>

                <div>
                  <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">API Key</label>
                  <input
                    type="password"
                    value={form.api_key || ''}
                    onChange={e => updateForm('api_key', e.target.value)}
                    placeholder="sk-..."
                    className={inputCls}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Max Tokens</label>
                    <input
                      type="number"
                      value={form.max_tokens || 4096}
                      onChange={e => updateForm('max_tokens', parseInt(e.target.value) || 4096)}
                      className={inputCls}
                    />
                  </div>
                  <div className="flex items-end pb-1">
                    <label className="flex items-center gap-2 text-sm text-[var(--color-text-main)] cursor-pointer">
                      <input
                        type="checkbox"
                        checked={form.is_default || false}
                        onChange={e => updateForm('is_default', e.target.checked)}
                        className="w-4 h-4 rounded border-[var(--color-border)] text-[var(--color-primary)] focus:ring-[var(--color-primary)]"
                      />
                      Set as default
                    </label>
                  </div>
                </div>

                <div>
                  <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Description</label>
                  <input
                    value={form.description || ''}
                    onChange={e => updateForm('description', e.target.value)}
                    placeholder="Optional description"
                    className={inputCls}
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 mt-6">
                <button
                  onClick={() => setShowAddModal(false)}
                  disabled={isCreating}
                  className="px-4 py-2 text-sm text-[var(--color-text-sec)] hover:bg-[var(--color-bg)] rounded-md transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreate}
                  disabled={isCreating}
                  className="px-4 py-2 text-sm bg-[var(--color-primary)] text-white rounded-md hover:bg-[var(--color-primary-hover)] transition-colors flex items-center gap-2 disabled:opacity-50"
                >
                  {isCreating && <Loader2 className="w-4 h-4 animate-spin" />}
                  {isCreating ? 'Creating...' : 'Create Model'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Edit Model Modal */}
      <AnimatePresence>
        {showEditModal && selectedModel && (
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
              className="bg-[var(--color-surface)] rounded-lg shadow-xl w-full max-w-lg p-6 border border-[var(--color-border)]"
            >
              <h3 className="text-lg font-semibold text-[var(--color-text-main)] mb-5">Edit Model</h3>

              {formError && (
                <div className="mb-4 p-2 bg-[var(--color-error)]/10 text-[var(--color-error)] text-sm rounded-md text-center">
                  {formError}
                </div>
              )}

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Name *</label>
                    <input
                      value={editForm.name || ''}
                      onChange={e => setEditForm(prev => ({ ...prev, name: e.target.value }))}
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Provider *</label>
                    <input
                      value={editForm.provider || ''}
                      onChange={e => setEditForm(prev => ({ ...prev, provider: e.target.value }))}
                      className={inputCls}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Model ID *</label>
                    <input
                      value={editForm.model_id || ''}
                      onChange={e => setEditForm(prev => ({ ...prev, model_id: e.target.value }))}
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Type</label>
                    <select
                      value={editForm.model_type || 'llm'}
                      onChange={e => setEditForm(prev => ({ ...prev, model_type: e.target.value }))}
                      className={inputCls}
                    >
                      <option value="llm">LLM</option>
                      <option value="embedding">Embedding</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">API Base</label>
                  <input
                    value={editForm.api_base || ''}
                    onChange={e => setEditForm(prev => ({ ...prev, api_base: e.target.value }))}
                    className={inputCls}
                  />
                </div>

                <div>
                  <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">API Key</label>
                  <input
                    type="password"
                    value={editForm.api_key || ''}
                    onChange={e => setEditForm(prev => ({ ...prev, api_key: e.target.value }))}
                    placeholder="Leave empty to keep current key"
                    className={inputCls}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Max Tokens</label>
                    <input
                      type="number"
                      value={editForm.max_tokens || 4096}
                      onChange={e => setEditForm(prev => ({ ...prev, max_tokens: parseInt(e.target.value) || 4096 }))}
                      className={inputCls}
                    />
                  </div>
                  <div className="flex items-end pb-1 gap-4">
                    <label className="flex items-center gap-2 text-sm text-[var(--color-text-main)] cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editForm.is_default || false}
                        onChange={e => setEditForm(prev => ({ ...prev, is_default: e.target.checked }))}
                        className="w-4 h-4 rounded border-[var(--color-border)] text-[var(--color-primary)] focus:ring-[var(--color-primary)]"
                      />
                      Default
                    </label>
                    <label className="flex items-center gap-2 text-sm text-[var(--color-text-main)] cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editForm.is_active !== false}
                        onChange={e => setEditForm(prev => ({ ...prev, is_active: e.target.checked }))}
                        className="w-4 h-4 rounded border-[var(--color-border)] text-[var(--color-primary)] focus:ring-[var(--color-primary)]"
                      />
                      Active
                    </label>
                  </div>
                </div>

                <div>
                  <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Description</label>
                  <input
                    value={editForm.description || ''}
                    onChange={e => setEditForm(prev => ({ ...prev, description: e.target.value }))}
                    className={inputCls}
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 mt-6">
                <button
                  onClick={() => { setShowEditModal(false); setSelectedModel(null); }}
                  disabled={isUpdating}
                  className="px-4 py-2 text-sm text-[var(--color-text-sec)] hover:bg-[var(--color-bg)] rounded-md transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleEdit}
                  disabled={isUpdating}
                  className="px-4 py-2 text-sm bg-[var(--color-primary)] text-white rounded-md hover:bg-[var(--color-primary-hover)] transition-colors flex items-center gap-2 disabled:opacity-50"
                >
                  {isUpdating && <Loader2 className="w-4 h-4 animate-spin" />}
                  {isUpdating ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-[var(--color-primary)] animate-spin" />
        </div>
      ) : (
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-sm overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[var(--color-bg)] border-b border-[var(--color-border)] text-xs text-[var(--color-text-sec)] font-semibold uppercase tracking-wider">
                <th className="px-4 py-3 w-[15%]">Name</th>
                <th className="px-4 py-3 w-[10%]">Type</th>
                <th className="px-4 py-3 w-[15%]">Provider</th>
                <th className="px-4 py-3 w-[20%]">Model ID</th>
                <th className="px-4 py-3 w-[15%]">Status</th>
                <th className="px-4 py-3 w-[10%] text-center">Default</th>
                <th className="px-4 py-3 w-[15%] text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="text-sm text-[var(--color-text-main)]">
              {models.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-[var(--color-text-sec)]">
                    No model configurations found. Click "Add Model" to create one.
                  </td>
                </tr>
              ) : (
                models.map((model) => (
                  <tr key={model.id} className="border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-bg)]/50 transition-colors">
                    <td className="px-4 py-3 font-medium">{model.name}</td>
                    <td className="px-4 py-3 text-xs text-[var(--color-text-sec)] uppercase">{model.model_type}</td>
                    <td className="px-4 py-3">{model.provider}</td>
                    <td className="px-4 py-3 text-xs text-[var(--color-text-mut)] font-mono">{model.model_id}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-[var(--color-success)]/15 text-[var(--color-success)]">
                        Active
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {model.is_default ? (
                        <button disabled className="cursor-default">
                          <Check className="w-4 h-4 text-[var(--color-success)] mx-auto" />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleSetDefault(model.id)}
                          className="text-[var(--color-text-mut)] hover:text-[var(--color-success)] transition-colors"
                          title="Set as default"
                        >
                          <span className="text-[10px]">Set Default</span>
                        </button>
                      )}
                    </td>
                    <td className="px-4 py-3 flex justify-end gap-3">
                      <button
                        onClick={() => handleTest(model.id)}
                        disabled={testing[model.id]}
                        className="text-[var(--color-text-sec)] hover:text-[var(--color-primary)] transition-colors disabled:opacity-50"
                        title="Test Connection"
                      >
                        {testing[model.id] ? <Loader2 className="w-4 h-4 animate-spin" /> : <Activity className="w-4 h-4" />}
                      </button>
                      <button
                        onClick={() => openEditModal(model)}
                        className="text-[var(--color-text-sec)] hover:text-[var(--color-primary)] transition-colors"
                        title="Edit"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(model.id)}
                        className="text-[var(--color-text-sec)] hover:text-[var(--color-error)] transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </motion.div>
  );
}
