import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Shield, Eye, EyeOff, Loader2 } from "lucide-react";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function Login() {
    const { login } = useAuth();
    const navigate = useNavigate();
    const [form, setForm] = useState({ username: "", password: "" });
    const [showPwd, setShowPwd] = useState(false);
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            await login(form.username, form.password);
            navigate("/dashboard");
        } catch (err) {
            toast.error(
                err.response?.data?.detail || "Identifiants incorrects",
            );
        } finally {
            setLoading(false);
        }
    };

    const fill = (role) => {
        setForm(
            role === "admin"
                ? { username: "admin", password: "admin123" }
                : role === "operator"
                  ? { username: "operator", password: "operator123" }
                  : { username: "viewer", password: "viewer123" },
        );
    };

    return (
        <div className="min-h-screen bg-linear-to-br from-gray-900 via-gray-800 to-orange-900 flex items-center justify-center p-4">
            <div className="w-full max-w-md">
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-600 rounded-2xl mb-4 shadow-xs-lg">
                        <Shield size={32} className="text-white" />
                    </div>
                    <h1 className="text-2xl font-bold text-white">
                        DocPlatform
                    </h1>
                    <p className="text-gray-400 text-sm mt-1">
                        Outil de Conformité
                    </p>
                </div>
                <div className="bg-white rounded-2xl shadow-xs-2xl p-8">
                    <h2 className="text-lg font-semibold text-gray-900 mb-6">
                        {" "}
                        Connexion
                    </h2>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <Field>
                            <FieldLabel htmlFor="input-field-username">
                                Nom d'utilisateur
                            </FieldLabel>
                            <Input
                                id="input-field-username"
                                type="text"
                                placeholder="admin"
                                value={form.username}
                                autocomplete="username"
                                onChange={(e) =>
                                    setForm({
                                        ...form,
                                        username: e.target.value,
                                    })
                                }
                                required
                                autoFocus
                            />
                        </Field>
                        <Field>
                            <FieldLabel htmlFor="input-field-password">
                                Mot de passe
                            </FieldLabel>
                            <div className="relative">
                                <Input
                                    className="pr-10"
                                    type={showPwd ? "text" : "password"}
                                    placeholder="••••••••"
                                    value={form.password}
                                    onChange={(e) =>
                                        setForm({
                                            ...form,
                                            password: e.target.value,
                                        })
                                    }
                                    required
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPwd(!showPwd)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                                >
                                    {showPwd ? (
                                        <EyeOff size={16} />
                                    ) : (
                                        <Eye size={16} />
                                    )}
                                </button>
                            </div>
                        </Field>
                        <Button type="submit" disabled={loading}>
                            {loading ? (
                                <>
                                    <Loader2
                                        size={16}
                                        className="animate-spin mr-2"
                                    />
                                    Connexion…
                                </>
                            ) : (
                                "Se connecter"
                            )}
                        </Button>
                    </form>
                    <div className="mt-6 pt-5 border-t border-gray-100">
                        <p className="text-xs text-gray-500 text-center mb-3">
                            Accès rapide démo
                        </p>
                        <div className="flex gap-2">
                            {["admin", "operator", "viewer"].map((r) => (
                                <Button
                                    key={r}
                                    variant="outline"
                                    size="sm"
                                    onClick={() => fill(r)}
                                    className="flex-1 capitalize"
                                >
                                    {r}
                                </Button>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
