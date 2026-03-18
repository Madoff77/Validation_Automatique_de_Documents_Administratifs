import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

import { Eye, EyeOff, Loader2, ScanText, ArrowRight } from "lucide-react";

import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";

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

    const fillDemo = (role) => {
        const creds = {
            admin: { username: "admin", password: "admin123" },
            operator: { username: "operator", password: "operator123" },
            viewer: { username: "viewer", password: "viewer123" },
        };
        setForm(creds[role]);
    };

    return (
        <div className="relative flex min-h-screen items-center justify-center overflow-hidden p-4 sm:p-6">
            <div className="absolute top-6 left-6 z-10 flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center shadow-md shrink-0 bg-primary">
                    <ScanText size={18} color="white" />
                </div>
                <div>
                    <div className="font-prata font-semibold text-base leading-tight">
                        DocPlatform
                    </div>
                    <div className="text-xs tracking-tighter text-muted-foreground">
                        Outil de Conformité
                    </div>
                </div>
            </div>
            <div className="form-in mt-16 grid w-full max-w-100 gap-6 px-1 sm:mt-0 sm:gap-7 sm:px-0">
                <div className="px-1 sm:px-0">
                    <div className="flex items-center gap-2 mb-1">
                        <div className="header-dot w-1.5 h-1.5 rounded-full bg-amber-500" />
                        <span className="text-xs text-muted-foreground uppercase tracking-widest font-medium">
                            Outil de Conformité
                        </span>
                    </div>
                    <h1 className="mb-1.5 font-prata text-[1.75rem] font-semibold leading-snug sm:text-[2rem]">
                        Connexion
                    </h1>
                    <p className="text-xs text-muted-foreground leading-normal">
                        Entrez vos identifiants pour accéder à votre espace
                    </p>
                </div>
                <form onSubmit={handleSubmit} className="px-1 sm:px-0">
                    <FieldGroup>
                        <Field>
                            <FieldLabel htmlFor="username">
                                Nom d'utilisateur
                            </FieldLabel>
                            <Input
                                id="username"
                                type="text"
                                placeholder="ex : martin.dupont"
                                value={form.username}
                                onChange={(e) =>
                                    setForm({
                                        ...form,
                                        username: e.target.value,
                                    })
                                }
                                required
                                autoFocus
                                autoComplete="username"
                            />
                        </Field>
                        <Field>
                            <FieldLabel htmlFor="password">
                                Mot de passe
                            </FieldLabel>
                            <div className="relative">
                                <Input
                                    id="password"
                                    type={showPwd ? "text" : "password"}
                                    placeholder="••••••••"
                                    value={form.password}
                                    onChange={(e) =>
                                        setForm({
                                            ...form,
                                            password: e.target.value,
                                        })
                                    }
                                    autoComplete="current-password"
                                    required
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPwd(!showPwd)}
                                    className="absolute right-4 top-1/2 -translate-y-1/2 bg-transparent text-primary border-none cursor-pointer p-0 flex items-center transition-colors duration-150"
                                >
                                    {showPwd ? (
                                        <EyeOff size={15} />
                                    ) : (
                                        <Eye size={15} />
                                    )}
                                </button>
                            </div>
                        </Field>
                        <Field orientation="horizontal">
                            <Button
                                type="submit"
                                size="lg"
                                disabled={loading}
                                className="w-full"
                            >
                                {loading ? (
                                    <>
                                        <Loader2
                                            size={15}
                                            className="spin"
                                        />
                                        Connexion…
                                    </>
                                ) : (
                                    <>
                                        <span>Se connecter</span>
                                        <ArrowRight size={15} />
                                    </>
                                )}
                            </Button>
                        </Field>
                    </FieldGroup>
                </form>
                <div className="grid grid-cols-1 gap-2 px-1 sm:grid-cols-3 sm:px-0">
                    {["admin", "operator", "viewer"].map((role) => (
                        <Button
                            key={role}
                            variant="outline"
                            size="sm"
                            className="flex-1 text-xs capitalize"
                            onClick={() => fillDemo(role)}
                        >
                            {role}
                        </Button>
                    ))}
                </div>
            </div>
        </div>
    );
}
