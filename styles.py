"""
Estilos CSS mejorados para la plataforma
"""

import streamlit as st

def inject_custom_css():
    """Inyecta CSS personalizado según el tema"""
    
    theme = st.session_state.get('theme', 'dark')
    
    if theme == 'dark':
        # Tema oscuro
        colors = {
            'bg_main': '#0d1117',
            'bg_secondary': '#161b22',
            'bg_card': '#1e1e1e',
            'text_primary': '#c9d1d9',
            'text_secondary': '#8b949e',
            'border': '#30363d',
            'accent': '#58a6ff',
            'accent_hover': '#79c0ff',
            'success': '#2ea043',
            'warning': '#d29922',
            'error': '#f85149',
            'info': '#58a6ff',
        }
    else:
        # Tema claro
        colors = {
            'bg_main': '#ffffff',
            'bg_secondary': '#f6f8fa',
            'bg_card': '#fafbfc',
            'text_primary': '#24292e',
            'text_secondary': '#586069',
            'border': '#e1e4e8',
            'accent': '#0969da',
            'accent_hover': '#1a7ae0',
            'success': '#1a7f37',
            'warning': '#9a6700',
            'error': '#cf222e',
            'info': '#0969da',
        }
    
    css = f"""
    <style>
        /* ===== ESTILOS BASE ===== */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        * {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }}
        
        .stApp {{
            background-color: {colors['bg_main']};
            color: {colors['text_primary']};
        }}
        
        [data-testid="stSidebar"] {{
            background-color: {colors['bg_secondary']};
            border-right: 1px solid {colors['border']};
        }}
        
        /* ===== TIPOGRAFÍA ===== */
        h1, h2, h3, h4, h5, h6 {{
            font-weight: 600;
            color: {colors['text_primary']};
            margin-bottom: 1rem;
        }}
        
        p {{
            line-height: 1.6;
            color: {colors['text_secondary']};
        }}
        
        /* ===== COMPONENTES STREAMLIT ===== */
        .stButton > button {{
            border-radius: 6px;
            border: 1px solid {colors['border']};
            background-color: {colors['bg_secondary']};
            color: {colors['text_primary']};
            font-weight: 500;
            padding: 0.5rem 1rem;
            transition: all 0.2s ease;
        }}
        
        .stButton > button:hover {{
            border-color: {colors['accent']};
            background-color: {colors['bg_card']};
        }}
        
        .stButton > button:focus {{
            box-shadow: 0 0 0 2px {colors['accent']}40;
        }}
        
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stSelectbox > div > div > select,
        .stNumberInput > div > div > input {{
            background-color: {colors['bg_secondary']};
            border: 1px solid {colors['border']};
            color: {colors['text_primary']};
            border-radius: 6px;
        }}
        
        .stTextInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus,
        .stSelectbox > div > div > select:focus,
        .stNumberInput > div > div > input:focus {{
            border-color: {colors['accent']};
            box-shadow: 0 0 0 2px {colors['accent']}40;
        }}
        
        /* ===== TARJETAS ===== */
        .card {{
            background-color: {colors['bg_card']};
            border: 1px solid {colors['border']};
            border-radius: 10px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            transition: all 0.3s ease;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        
        .card:hover {{
            border-color: {colors['accent']};
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            transform: translateY(-2px);
        }}
        
        .card-title {{
            color: {colors['accent']};
            font-weight: 600;
            font-size: 1.1rem;
            margin-bottom: 0.5rem;
        }}
        
        .card-content {{
            color: {colors['text_secondary']};
            font-size: 0.9rem;
            line-height: 1.5;
        }}
        
        /* ===== TARJETAS DE CURSO ===== */
        .course-card {{
            background-color: {colors['bg_card']};
            border: 1px solid {colors['border']};
            border-radius: 12px;
            overflow: hidden;
            transition: all 0.3s ease;
            margin-bottom: 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .course-card:hover {{
            border-color: {colors['accent']};
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
            transform: translateY(-5px);
        }}
        
        .course-card-image {{
            height: 160px;
            width: 100%;
            object-fit: cover;
            background: linear-gradient(135deg, {colors['accent']}20, {colors['accent']}40);
        }}
        
        .course-card-content {{
            padding: 1.25rem;
        }}
        
        .course-card-title {{
            color: {colors['accent']};
            font-weight: 600;
            font-size: 1.1rem;
            margin-bottom: 0.5rem;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}
        
        .course-card-description {{
            color: {colors['text_secondary']};
            font-size: 0.9rem;
            line-height: 1.5;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
            margin-bottom: 1rem;
        }}
        
        .course-card-meta {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.85rem;
            color: {colors['text_secondary']};
        }}
        
        /* ===== BADGES ===== */
        .badge {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .badge-success {{
            background-color: {colors['success']}20;
            color: {colors['success']};
            border: 1px solid {colors['success']}40;
        }}
        
        .badge-warning {{
            background-color: {colors['warning']}20;
            color: {colors['warning']};
            border: 1px solid {colors['warning']}40;
        }}
        
        .badge-error {{
            background-color: {colors['error']}20;
            color: {colors['error']};
            border: 1px solid {colors['error']}40;
        }}
        
        .badge-info {{
            background-color: {colors['info']}20;
            color: {colors['info']};
            border: 1px solid {colors['info']}40;
        }}
        
        .badge-accent {{
            background-color: {colors['accent']}20;
            color: {colors['accent']};
            border: 1px solid {colors['accent']}40;
        }}
        
        /* ===== PROGRESS BARS ===== */
        .stProgress > div > div > div {{
            background-color: {colors['accent']};
        }}
        
        /* ===== MEJORAS DE PERFORMANCE ===== */
        .stDataFrame {{
            border: 1px solid {colors['border']};
            border-radius: 8px;
            overflow: hidden;
        }}
        
        /* Optimización de imágenes */
        img {{
            max-width: 100%;
            height: auto;
            loading: lazy;
        }}
        
        /* Mejoras de accesibilidad */
        button:focus,
        input:focus,
        textarea:focus,
        select:focus {{
            outline: 2px solid {colors['accent']};
            outline-offset: 2px;
        }}
        
        /* Indicadores de carga */
        .loading-spinner {{
            border: 3px solid {colors['border']};
            border-top: 3px solid {colors['accent']};
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }}
        
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        
        /* Mejoras para dispositivos móviles */
        @media (max-width: 480px) {{
            .stButton > button {{
                padding: 0.75rem 1rem;
                font-size: 0.9rem;
            }}
            
            .card {{
                padding: 1rem;
                margin-bottom: 0.75rem;
            }}
        }}
        
        /* Estados de error mejorados */
        .error-container {{
            background-color: {colors['error']}10;
            border: 1px solid {colors['error']}40;
            border-radius: 8px;
            padding: 1rem;
            margin: 1rem 0;
        }}
        
        .success-container {{
            background-color: {colors['success']}10;
            border: 1px solid {colors['success']}40;
            border-radius: 8px;
            padding: 1rem;
            margin: 1rem 0;
        }}
        
        /* ===== TABLAS ===== */
        .stDataFrame {{
            border: 1px solid {colors['border']};
            border-radius: 8px;
            overflow: hidden;
        }}
        
        /* ===== ALERTAS ===== */
        .stAlert {{
            border-radius: 8px;
            border-left: 4px solid;
        }}
        
        .stAlert[data-baseweb="notification"] {{
            background-color: {colors['info']}10;
            border-left-color: {colors['info']};
        }}
        
        /* ===== SIDEBAR ===== */
        .sidebar-user {{
            display: flex;
            align-items: center;
            padding: 1rem;
            border-bottom: 1px solid {colors['border']};
            margin-bottom: 1.5rem;
        }}
        
        .sidebar-user img {{
            border-radius: 50%;
            margin-right: 1rem;
            border: 2px solid {colors['accent']};
        }}
        
        /* ===== FORMULARIOS ===== */
        .stForm {{
            background-color: {colors['bg_secondary']};
            border: 1px solid {colors['border']};
            border-radius: 10px;
            padding: 1.5rem;
        }}
        
        /* ===== RESPONSIVIDAD ===== */
        @media (max-width: 768px) {{
            .course-card {{
                margin-bottom: 1rem;
            }}
            
            .card {{
                padding: 1rem;
            }}
            
            h1 {{
                font-size: 1.5rem;
            }}
            
            h2 {{
                font-size: 1.25rem;
            }}
        }}
        
        /* ===== ANIMACIONES ===== */
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .animate-fade-in {{
            animation: fadeIn 0.3s ease-out;
        }}
        
        /* ===== SCROLLBAR ===== */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        
        ::-webkit-scrollbar-track {{
            background: {colors['bg_secondary']};
        }}
        
        ::-webkit-scrollbar-thumb {{
            background: {colors['border']};
            border-radius: 4px;
        }}
        
        ::-webkit-scrollbar-thumb:hover {{
            background: {colors['accent']};
        }}
        
        /* ===== UTILIDADES ===== */
        .text-accent {{
            color: {colors['accent']};
        }}
        
        .text-success {{
            color: {colors['success']};
        }}
        
        .text-warning {{
            color: {colors['warning']};
        }}
        
        .text-error {{
            color: {colors['error']};
        }}
        
        .bg-accent {{
            background-color: {colors['accent']}20;
        }}
        
        .border-accent {{
            border-color: {colors['accent']};
        }}
        
        /* ===== BOTONES ESPECIALES ===== */
        .btn-primary {{
            background-color: {colors['accent']} !important;
            color: white !important;
            border-color: {colors['accent']} !important;
        }}
        
        .btn-primary:hover {{
            background-color: {colors['accent_hover']} !important;
            border-color: {colors['accent_hover']} !important;
        }}
        
        /* ===== TOOLTIPS ===== */
        .tooltip {{
            position: relative;
            display: inline-block;
        }}
        
        .tooltip .tooltiptext {{
            visibility: hidden;
            background-color: {colors['bg_card']};
            color: {colors['text_primary']};
            text-align: center;
            padding: 5px 10px;
            border-radius: 6px;
            border: 1px solid {colors['border']};
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            transform: translateX(-50%);
            white-space: nowrap;
            font-size: 0.8rem;
        }}
        
        .tooltip:hover .tooltiptext {{
            visibility: visible;
        }}
        
        /* ===== SOBRESCRIBIR FONDOS VERDES/CLAROS ===== */
        [data-testid="stExpander"] {{
            background-color: transparent !important;
            border: none !important;
        }}
        
        [data-testid="stExpander"] > div {{
            background-color: transparent !important;
        }}
        
        [data-testid="stExpander"] > div > div {{
            background-color: transparent !important;
        }}
        
        [data-testid="stExpander"] > div > div > div {{
            background-color: transparent !important;
        }}
        
        /* Asegurar que el contenido HTML tenga fondo oscuro */
        .stMarkdown {{
            background-color: transparent !important;
        }}
        
        /* Sobrescribir cualquier fondo claro en divs */
        div[style*="background: rgb"] {{
            background: transparent !important;
        }}
        
        /* Forzar transparencia en todos los contenedores del expander */
        .streamlit-expanderHeader {{
            background-color: {colors['bg_secondary']} !important;
        }}
        
        .streamlit-expanderContent {{
            background-color: transparent !important;
        }}
    </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)
    
    # JavaScript adicional para mejoras de UI
    js = """
    <script>
        // Mejorar experiencia de formularios
        document.addEventListener('DOMContentLoaded', function() {
            // Agregar clases a elementos específicos
            const cards = document.querySelectorAll('[data-testid="stExpander"]');
            cards.forEach(card => {
                card.classList.add('animate-fade-in');
            });
            
            // Mejorar botones de envío
            const submitButtons = document.querySelectorAll('button[kind="primaryFormSubmit"]');
            submitButtons.forEach(btn => {
                btn.classList.add('btn-primary');
            });
        });
        
        // Prevenir envío doble de formularios
        let forms = document.querySelectorAll('form');
        forms.forEach(form => {
            form.addEventListener('submit', function(e) {
                let submitBtn = this.querySelector('button[type="submit"]');
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = 'Procesando...';
                    setTimeout(() => {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = submitBtn.getAttribute('data-original-text') || 'Enviar';
                    }, 3000);
                }
            });
        });
    </script>
    """
    
    st.markdown(js, unsafe_allow_html=True)