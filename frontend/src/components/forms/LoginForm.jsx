export default function LoginForm({ form, setForm, error, loading, onSubmit }) {
    return (
        <form onSubmit={onSubmit} className="space-y-4">

            {error && (
                <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3">
                    {error}
                </div>
            )}

            <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email or Username
                </label>
                <input
                    type="text"
                    placeholder="Enter email or username"
                    required
                    autoComplete="username"
                    className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={form.identifier}
                    onChange={e => setForm({ ...form, identifier: e.target.value })}
                />
            </div>

            <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                    Password
                </label>
                <input
                    type="password"
                    placeholder="Enter password"
                    required
                    autoComplete="current-password"
                    className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={form.password}
                    onChange={e => setForm({ ...form, password: e.target.value })}
                />
            </div>

            <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                    <input
                        type="checkbox"
                        checked={form.remember_me}
                        onChange={e => setForm({ ...form, remember_me: e.target.checked })}
                        className="rounded border-gray-300"
                    />
                    Remember Me
                </label>
            </div>

            <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 text-white py-2.5 rounded-lg hover:bg-blue-700 transition font-medium text-sm disabled:opacity-50"
            >
                {loading ? (
                    <span className="flex items-center justify-center gap-2">
                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                            <circle className="opacity-25" cx="12" cy="12" r="10"
                                    stroke="currentColor" strokeWidth="4"/>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                        </svg>
                        Signing in...
                    </span>
                ) : "Sign In"}
            </button>
        </form>
    );
}