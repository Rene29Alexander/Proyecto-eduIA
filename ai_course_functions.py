# -*- coding: utf-8 -*-
"""
Funciones para el sistema de cursos IA
Todas las mejoras implementadas aquí
"""

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime

def fix_language_in_text(text, correct_language):
    """Corrige menciones incorrectas de lenguajes en el texto y limpia caracteres mal codificados"""
    if not text:
        return text
    
    # Limpiar caracteres mal codificados
    replacements = {
        ''': "'",  # Apóstrofe curvo izquierdo
        ''': "'",  # Apóstrofe curvo derecho
        '"': '"',  # Comilla doble curva izquierda
        '"': '"',  # Comilla doble curva derecha
        '`': "'",  # Acento grave
        '´': "'",  # Acento agudo
        '–': '-',  # Guión medio
        '—': '-',  # Guión largo
        '…': '...',  # Puntos suspensivos
        '«': '"',  # Comilla angular izquierda
        '»': '"',  # Comilla angular derecha
        '‹': "'",  # Comilla angular simple izquierda
        '›': "'",  # Comilla angular simple derecha
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text

def render_course_sections(conn, user, model, ai_course, sections_rows):
    """Renderiza las secciones del curso con diseño mejorado"""
    
    # CSS para sobrescribir el fondo verde del expander
    st.markdown("""
    <style>
    /* Sobrescribir fondo del expander */
    [data-testid="stExpander"] {
        background-color: transparent !important;
        border: none !important;
    }
    [data-testid="stExpander"] > div {
        background-color: transparent !important;
    }
    [data-testid="stExpander"] > div > div {
        background-color: transparent !important;
    }
    /* Sobrescribir cualquier fondo verde */
    div[style*="background"] {
        background: transparent !important;
    }
    /* Forzar fondo oscuro en el contenido */
    .stMarkdown {
        background-color: transparent !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="text-align: center; margin: 20px 0;">
        <h2 style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.5em;
            font-weight: bold;
            margin: 0;
        ">📚 Secciones del Curso</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Info box con diseño mejorado
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 30px;
        color: white;
        text-align: center;
        box-shadow: 0 8px 16px rgba(102, 126, 234, 0.3);
    ">
        <h3 style="margin: 0 0 10px 0; font-size: 1.3em;">💡 Completa cada sección en orden</h3>
        <p style="margin: 0; font-size: 1.1em; opacity: 0.95;">
            Estudia el contenido y usa el Chat IA para resolver tus dudas
        </p>
    </div>
    """, unsafe_allow_html=True)

    
    for section_row in sections_rows:
        section = dict(section_row) if not isinstance(section_row, dict) else section_row
        section_id = section['id']
        section_number = section['topic_number']
        is_unlocked = section.get('is_unlocked', 0)
        is_completed = section.get('is_completed', 0)
        
        # Icono y color de estado
        if is_completed:
            status_icon = "✅"
            status_text = "Completada"
            status_color = "#28a745"
            border_color = "#28a745"
        elif is_unlocked:
            status_icon = "📖"
            status_text = "En Progreso"
            status_color = "#ffc107"
            border_color = "#ffc107"
        else:
            status_icon = "🔒"
            status_text = "Bloqueada"
            status_color = "#6c757d"
            border_color = "#6c757d"
        
        # Card de la sección
        st.markdown(f"""
        <div style="
            border-left: 6px solid {border_color};
            background: linear-gradient(135deg, #2d2d2d 0%, #1a1a1a 100%);
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 20px;
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.3);
        ">
            <h2 style="color: white; margin: 0 0 10px 0; font-size: 1.8em;">
                {status_icon} Sección {section_number}: {fix_language_in_text(section['title'], ai_course['language'])}
            </h2>
            <p style="color: {status_color}; margin: 0; font-size: 1.1em; font-weight: 600;">
                {status_text}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # OPTIMIZACIÓN: Solo renderizar contenido si está desbloqueada
        # Esto previene que se ejecuten queries pesadas para secciones bloqueadas
        if not is_unlocked:
            with st.expander(f"Ver Sección {section_number}", expanded=False):
                st.warning("🔒 Completa la sección anterior para desbloquear")
            continue
        
        # Usar session_state para controlar qué expander está abierto
        expander_key = f"section_expander_{section_id}"
        is_expanded = st.session_state.get(expander_key, is_unlocked and not is_completed)
        
        with st.expander(f"Ver Sección {section_number}", expanded=is_expanded):
            # Descripción
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #2d2d2d 0%, #1a1a1a 100%);
                padding: 20px;
                border-radius: 15px;
                margin-bottom: 20px;
                border-left: 5px solid #667eea;
            ">
                <h4 style="color: #e0e0e0; margin: 0 0 10px 0;">📝 Descripción</h4>
                <p style="color: #d0d0d0; margin: 0;">{fix_language_in_text(section.get('description', ''), ai_course['language'])}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if section.get('objectives'):
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #1a2332 0%, #0f1923 100%);
                    padding: 20px;
                    border-radius: 15px;
                    margin-bottom: 20px;
                    border-left: 5px solid #0066cc;
                ">
                    <h4 style="color: #4da6ff; margin: 0 0 10px 0;">🎯 Objetivos</h4>
                    <p style="color: #b3d9ff; margin: 0;">{fix_language_in_text(section['objectives'], ai_course['language'])}</p>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Tabs - Solo Contenido y Chat IA
            sec_tab1, sec_tab2 = st.tabs(["📚 Contenido", "💬 Chat IA"])
            
            with sec_tab1:
                render_section_content(conn, user, section, ai_course)
            
            with sec_tab2:
                render_section_chat(conn, user, model, section, ai_course)



def render_section_content(conn, user, section, ai_course):
    """Renderiza el contenido de la lección y recursos externos"""
    
    section_id = section['id']
    
    # PRIMERA PARTE: Mostrar contenido HTML de la lección (el excelente)
    lesson_material = conn.execute("""
        SELECT * FROM ai_course_materials 
        WHERE topic_id = ? AND type = 'tutorial'
        LIMIT 1
    """, (section_id,)).fetchone()
    
    if lesson_material:
        lesson_dict = dict(lesson_material)
        lesson_content = lesson_dict.get('description', '')
        
        if lesson_content:
            # Decodificar contenido HTML
            import html
            lesson_content_decoded = html.unescape(lesson_content)
            
            # Renderizar con el estilo profesional completo
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    * {{
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }}
                    
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                        background: #0a0a0f;
                        color: #e4e4e7;
                        line-height: 1.6;
                    }}
                    
                    .lesson-container {{
                        width: 100%;
                        margin: 0;
                        padding: 48px 40px;
                        background: linear-gradient(135deg, #1a1a24 0%, #0f0f16 100%);
                        border-radius: 0;
                        border: none;
                        box-shadow: none;
                        min-height: 400px;
                        position: relative;
                        overflow: hidden;
                    }}
                    
                    /* Barra superior con efecto glassmorphism */
                    .lesson-container::before {{
                        content: '';
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        height: 3px;
                        background: linear-gradient(90deg, 
                            #3b82f6 0%, 
                            #8b5cf6 25%, 
                            #ec4899 50%, 
                            #f59e0b 75%, 
                            #10b981 100%
                        );
                        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.5);
                    }}
                    
                    /* Efecto de grid en el fondo */
                    .lesson-container::after {{
                        content: '';
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        bottom: 0;
                        background-image: 
                            linear-gradient(rgba(59, 130, 246, 0.03) 1px, transparent 1px),
                            linear-gradient(90deg, rgba(59, 130, 246, 0.03) 1px, transparent 1px);
                        background-size: 50px 50px;
                        pointer-events: none;
                        z-index: 0;
                    }}
                    
                    .lesson-container > * {{
                        position: relative;
                        z-index: 1;
                    }}
                    
                    /* Títulos principales con efecto neón */
                    h1 {{
                        color: #ffffff;
                        margin: 0 0 40px 0;
                        font-size: 2.75em;
                        font-weight: 800;
                        letter-spacing: -1px;
                        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 50%, #ec4899 100%);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                        background-clip: text;
                        padding-bottom: 24px;
                        border-bottom: 1px solid rgba(59, 130, 246, 0.2);
                        text-shadow: 0 0 30px rgba(59, 130, 246, 0.3);
                        position: relative;
                    }}
                    
                    h1::after {{
                        content: '';
                        position: absolute;
                        bottom: -1px;
                        left: 0;
                        width: 120px;
                        height: 3px;
                        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
                        border-radius: 2px;
                        box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
                    }}
                    
                    /* Secciones con diseño de tarjeta */
                    h2 {{
                        color: #f8fafc;
                        margin: 48px 0 24px 0;
                        font-size: 1.875em;
                        font-weight: 700;
                        letter-spacing: -0.5px;
                        padding: 16px 24px;
                        background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.05) 100%);
                        border-left: 4px solid #3b82f6;
                        border-radius: 8px;
                        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
                        position: relative;
                        overflow: hidden;
                    }}
                    
                    h2::before {{
                        content: '▸';
                        position: absolute;
                        left: 8px;
                        color: #3b82f6;
                        font-size: 0.8em;
                    }}
                    
                    h3 {{
                        color: #e2e8f0;
                        margin: 36px 0 18px 0;
                        font-size: 1.5em;
                        font-weight: 600;
                        letter-spacing: -0.3px;
                        padding-left: 20px;
                        border-left: 3px solid #8b5cf6;
                        position: relative;
                    }}
                    
                    h3::before {{
                        content: '›';
                        position: absolute;
                        left: 6px;
                        color: #8b5cf6;
                        font-size: 0.9em;
                    }}
                    
                    h4 {{
                        color: #cbd5e1;
                        margin: 28px 0 14px 0;
                        font-size: 1.25em;
                        font-weight: 600;
                        letter-spacing: -0.2px;
                        padding-left: 16px;
                        border-left: 2px solid #ec4899;
                    }}
                    
                    /* Párrafos con mejor legibilidad */
                    p {{
                        color: #cbd5e1;
                        line-height: 1.8;
                        margin-bottom: 20px;
                        font-size: 1.0625em;
                        font-weight: 400;
                        text-align: justify;
                    }}
                    
                    /* Listas con iconos personalizados */
                    ul, ol {{
                        color: #cbd5e1;
                        line-height: 1.8;
                        margin-left: 32px;
                        margin-bottom: 24px;
                        font-size: 1.0625em;
                    }}
                    
                    li {{
                        margin-bottom: 14px;
                        color: #cbd5e1;
                        padding-left: 12px;
                        position: relative;
                    }}
                    
                    ul li::marker {{
                        content: '▹ ';
                        color: #3b82f6;
                        font-weight: 700;
                        font-size: 1.2em;
                    }}
                    
                    ol li::marker {{
                        color: #8b5cf6;
                        font-weight: 700;
                    }}
                    
                    /* Bloques de código profesionales */
                    pre {{
                        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                        border: 1px solid rgba(59, 130, 246, 0.2);
                        border-radius: 12px;
                        padding: 0;
                        overflow: hidden;
                        margin: 32px 0;
                        box-shadow: 
                            0 10px 15px -3px rgba(0, 0, 0, 0.5),
                            0 4px 6px -2px rgba(0, 0, 0, 0.3),
                            0 0 0 1px rgba(59, 130, 246, 0.1) inset;
                        position: relative;
                    }}
                    
                    /* Barra superior del bloque de código */
                    pre::before {{
                        content: '';
                        display: block;
                        height: 40px;
                        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
                        border-bottom: 1px solid rgba(59, 130, 246, 0.2);
                        position: relative;
                    }}
                    
                    /* Botones de ventana en el código */
                    pre::after {{
                        content: '';
                        position: absolute;
                        top: 14px;
                        left: 16px;
                        width: 12px;
                        height: 12px;
                        background: #ef4444;
                        border-radius: 50%;
                        box-shadow: 
                            18px 0 0 #f59e0b,
                            36px 0 0 #10b981;
                    }}
                    
                    code {{
                        color: #e2e8f0;
                        font-family: 'Fira Code', 'JetBrains Mono', 'Courier New', monospace;
                        font-size: 0.9375em;
                        font-weight: 400;
                        letter-spacing: 0;
                        line-height: 1.7;
                        font-feature-settings: 'liga' 1, 'calt' 1;
                    }}
                    
                    pre code {{
                        display: block;
                        padding: 24px;
                        overflow-x: auto;
                        background: transparent;
                        color: #e2e8f0;
                    }}
                    
                    /* Syntax highlighting mejorado */
                    pre code .keyword {{ color: #c792ea; font-weight: 500; }}
                    pre code .string {{ color: #c3e88d; }}
                    pre code .comment {{ color: #546e7a; font-style: italic; }}
                    pre code .function {{ color: #82aaff; }}
                    pre code .number {{ color: #f78c6c; }}
                    pre code .operator {{ color: #89ddff; }}
                    
                    /* Código inline elegante */
                    :not(pre) > code {{
                        background: rgba(59, 130, 246, 0.12);
                        padding: 3px 10px;
                        border-radius: 6px;
                        font-size: 0.9em;
                        color: #60a5fa;
                        border: 1px solid rgba(59, 130, 246, 0.2);
                        font-family: 'Fira Code', monospace;
                        font-weight: 500;
                        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
                    }}
                    
                    /* Texto destacado */
                    strong {{
                        color: #fbbf24;
                        font-weight: 700;
                        text-shadow: 0 0 20px rgba(251, 191, 36, 0.3);
                    }}
                    
                    em {{
                        color: #60a5fa;
                        font-style: italic;
                        font-weight: 500;
                    }}
                    
                    /* Blockquotes profesionales */
                    blockquote {{
                        background: linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(139, 92, 246, 0.08) 100%);
                        border-left: 4px solid #3b82f6;
                        padding: 24px 28px;
                        margin: 32px 0;
                        border-radius: 8px;
                        color: #cbd5e1;
                        font-style: italic;
                        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
                        position: relative;
                        overflow: hidden;
                    }}
                    
                    blockquote::before {{
                        content: '"';
                        position: absolute;
                        top: -10px;
                        left: 12px;
                        font-size: 5em;
                        color: rgba(59, 130, 246, 0.15);
                        font-family: Georgia, serif;
                        line-height: 1;
                        font-weight: 700;
                    }}
                    
                    blockquote::after {{
                        content: '';
                        position: absolute;
                        top: 0;
                        right: 0;
                        width: 100px;
                        height: 100%;
                        background: linear-gradient(90deg, transparent 0%, rgba(59, 130, 246, 0.05) 100%);
                        pointer-events: none;
                    }}
                    
                    /* Enlaces con efecto hover */
                    a {{
                        color: #60a5fa;
                        text-decoration: none;
                        border-bottom: 2px solid transparent;
                        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                        font-weight: 500;
                        position: relative;
                    }}
                    
                    a::after {{
                        content: '';
                        position: absolute;
                        bottom: -2px;
                        left: 0;
                        width: 0;
                        height: 2px;
                        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
                        transition: width 0.3s ease;
                    }}
                    
                    a:hover {{
                        color: #93c5fd;
                    }}
                    
                    a:hover::after {{
                        width: 100%;
                    }}
                    
                    /* Tablas profesionales */
                    table {{
                        width: 100%;
                        border-collapse: separate;
                        border-spacing: 0;
                        margin: 32px 0;
                        background: rgba(15, 23, 42, 0.5);
                        border-radius: 12px;
                        overflow: hidden;
                        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
                        border: 1px solid rgba(59, 130, 246, 0.2);
                    }}
                    
                    thead {{
                        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
                    }}
                    
                    th {{
                        color: #f8fafc;
                        padding: 16px 20px;
                        text-align: left;
                        font-weight: 700;
                        font-size: 0.9375em;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                        border-bottom: 2px solid rgba(59, 130, 246, 0.3);
                    }}
                    
                    td {{
                        padding: 16px 20px;
                        border-bottom: 1px solid rgba(59, 130, 246, 0.1);
                        color: #cbd5e1;
                        font-size: 0.9375em;
                    }}
                    
                    tbody tr {{
                        transition: all 0.2s ease;
                    }}
                    
                    tbody tr:hover {{
                        background: rgba(59, 130, 246, 0.08);
                    }}
                    
                    tr:last-child td {{
                        border-bottom: none;
                    }}
                    
                    /* Separadores elegantes */
                    hr {{
                        border: none;
                        height: 1px;
                        background: linear-gradient(90deg, 
                            transparent 0%, 
                            rgba(59, 130, 246, 0.3) 20%, 
                            rgba(139, 92, 246, 0.3) 50%, 
                            rgba(236, 72, 153, 0.3) 80%, 
                            transparent 100%
                        );
                        margin: 48px 0;
                        position: relative;
                    }}
                    
                    hr::after {{
                        content: '◆';
                        position: absolute;
                        top: 50%;
                        left: 50%;
                        transform: translate(-50%, -50%);
                        background: #0a0a0f;
                        padding: 0 16px;
                        color: #3b82f6;
                        font-size: 0.75em;
                    }}
                    
                    /* Scrollbar personalizado */
                    ::-webkit-scrollbar {{
                        width: 12px;
                        height: 12px;
                    }}
                    
                    ::-webkit-scrollbar-track {{
                        background: rgba(15, 23, 42, 0.5);
                        border-radius: 6px;
                    }}
                    
                    ::-webkit-scrollbar-thumb {{
                        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
                        border-radius: 6px;
                        border: 2px solid rgba(15, 23, 42, 0.5);
                    }}
                    
                    ::-webkit-scrollbar-thumb:hover {{
                        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
                    }}
                    
                    /* Animaciones sutiles */
                    @keyframes fadeInUp {{
                        from {{
                            opacity: 0;
                            transform: translateY(20px);
                        }}
                        to {{
                            opacity: 1;
                            transform: translateY(0);
                        }}
                    }}
                    
                    @keyframes pulse {{
                        0%, 100% {{
                            opacity: 1;
                        }}
                        50% {{
                            opacity: 0.8;
                        }}
                    }}
                    
                    .lesson-container > * {{
                        animation: fadeInUp 0.6s ease-out;
                    }}
                    
                    /* Notas y alertas */
                    .note {{
                        background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%);
                        border-left: 4px solid #3b82f6;
                        padding: 20px 24px;
                        margin: 24px 0;
                        border-radius: 8px;
                        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
                    }}
                    
                    .warning {{
                        background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(245, 158, 11, 0.05) 100%);
                        border-left: 4px solid #f59e0b;
                        padding: 20px 24px;
                        margin: 24px 0;
                        border-radius: 8px;
                        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
                    }}
                    
                    .success {{
                        background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(16, 185, 129, 0.05) 100%);
                        border-left: 4px solid #10b981;
                        padding: 20px 24px;
                        margin: 24px 0;
                        border-radius: 8px;
                        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
                    }}
                    
                    /* Responsive */
                    @media (max-width: 768px) {{
                        .lesson-container {{
                            padding: 32px 24px;
                        }}
                        
                        h1 {{
                            font-size: 2em;
                        }}
                        
                        h2 {{
                            font-size: 1.5em;
                        }}
                        
                        pre code {{
                            font-size: 0.875em;
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="lesson-container">
                    {lesson_content_decoded}
                </div>
            </body>
            </html>
            """
            
            # Calcular altura aproximada
            import re
            num_headings = len(re.findall(r'<h[1-6]', lesson_content_decoded))
            num_paragraphs = len(re.findall(r'<p>', lesson_content_decoded))
            num_code_blocks = len(re.findall(r'<pre>', lesson_content_decoded))
            num_lists = len(re.findall(r'<ul>|<ol>', lesson_content_decoded))
            
            estimated_height = 400 + (num_headings * 60) + (num_paragraphs * 80) + (num_code_blocks * 200) + (num_lists * 150)
            estimated_height = max(1000, min(5000, estimated_height))
            
            # Renderizar contenido HTML
            components.html(html_content, height=estimated_height, scrolling=True)
    
    st.markdown("---")
    
    # SEGUNDA PARTE: Recursos con pestañas
    st.markdown("""
    <div style="text-align: center; margin: 30px 0 20px 0;">
        <h2 style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.2em;
            font-weight: bold;
        ">📚 Recursos de Aprendizaje</h2>
        <p style="color: #666; margin: 10px 0 0 0;">
            Materiales recomendados para estudiar este tema
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Crear pestañas para recursos
    tab1, tab2 = st.tabs(["📦 Recursos del Curso", "🌐 Recursos Externos Recomendados"])
    
    with tab1:
        # Obtener materiales complementarios (excluyendo tutorial)
        materials = conn.execute("""
            SELECT * FROM ai_course_materials 
            WHERE topic_id = ? AND type != 'tutorial'
            ORDER BY order_index
        """, (section_id,)).fetchall()
        
        if not materials:
            st.info("📭 No hay recursos disponibles para esta sección aún")
        else:
            for mat_row in materials:
                mat = dict(mat_row)
                mat_id = mat['id']
                mat_type = mat.get('type', 'website')
                mat_url = mat.get('url', '#')
                is_completed = mat.get('is_completed', 0)
                
                icon_map = {
                    'video': '🎥',
                    'website': '🌐',
                    'tutorial': '📖',
                    'documentation': '📄'
                }
                icon = icon_map.get(mat_type, '📄')
                
                gradient_map = {
                    'video': 'linear-gradient(135deg, #ff0844 0%, #ffb199 100%)',
                    'website': 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
                    'tutorial': 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
                    'documentation': 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)'
                }
                gradient = gradient_map.get(mat_type, 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)')
                
                # Expander colapsable
                with st.expander(f"{icon} {fix_language_in_text(mat['title'], ai_course['language'])}" + (" ✅" if is_completed else ""), expanded=False):
                    st.markdown(f"""
                    <div style="
                        background: {gradient};
                        padding: 20px;
                        border-radius: 15px;
                        margin-bottom: 15px;
                    ">
                        <p style="color: rgba(255, 255, 255, 0.95); margin: 0 0 10px 0; font-size: 1.05em; line-height: 1.5;">
                            {fix_language_in_text(mat.get('description', ''), ai_course['language'])}
                        </p>
                        <p style="color: rgba(255, 255, 255, 0.85); margin: 0; font-size: 0.95em;">
                            ⏱️ Tiempo estimado: <strong>{mat.get('estimated_minutes', 30)} minutos</strong>
                        </p>
                    </div>
                    """, unsafe_allow_html=True)                
                    # Si es video, mostrar embebido
                    if mat_type == 'video' and mat_url and mat_url != '#':
                        # Si es búsqueda de YouTube
                        if 'youtube.com/results?search_query=' in mat_url:
                            search_terms = mat_url.split('search_query=')[1].replace('+', ' ')
                            st.markdown(f"""
                            <div style="
                                background: linear-gradient(135deg, #ff0000 0%, #cc0000 100%);
                                padding: 20px;
                                border-radius: 15px;
                                text-align: center;
                                margin: 10px 0;
                            ">
                                <h4 style="color: white; margin: 0 0 10px 0;">🎥 Video Tutorial en YouTube</h4>
                                <p style="color: #ffcccc; margin: 0 0 15px 0;">Buscar: {search_terms}</p>
                                <a href="{mat_url}" target="_blank" style="
                                    display: inline-block;
                                    padding: 12px 30px;
                                    background: white;
                                    color: #ff0000;
                                    text-decoration: none;
                                    border-radius: 25px;
                                    font-weight: bold;
                                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
                                ">
                                    ▶️ Ver Videos en YouTube
                                </a>
                            </div>
                            """, unsafe_allow_html=True)
                        # Si es video directo de YouTube
                        elif 'youtube.com/watch?v=' in mat_url or 'youtu.be/' in mat_url:
                            video_id = None
                            if 'youtube.com/watch?v=' in mat_url:
                                video_id = mat_url.split('watch?v=')[1].split('&')[0]
                            elif 'youtu.be/' in mat_url:
                                video_id = mat_url.split('youtu.be/')[1].split('?')[0]
                            
                            if video_id:
                                st.markdown(f"""
                                <div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; background: #000; border-radius: 15px; box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3); margin: 15px 0;">
                                    <iframe 
                                        src="https://www.youtube.com/embed/{video_id}"
                                        style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border-radius: 15px;"
                                        frameborder="0"
                                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                        allowfullscreen>
                                    </iframe>
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <a href="{mat_url}" target="_blank" style="
                                display: inline-block;
                                width: 100%;
                                padding: 15px;
                                background: linear-gradient(135deg, #ff0000 0%, #cc0000 100%);
                                color: white;
                                text-align: center;
                                text-decoration: none;
                                border-radius: 15px;
                                font-weight: bold;
                                margin: 10px 0;
                            ">
                                🎥 Ver Video
                            </a>
                            """, unsafe_allow_html=True)
                    
                    # Si es website, tutorial o documentación
                    else:
                        # Verificar si la URL es válida
                        if mat_url and mat_url != '#' and 'ejemplo.com' not in mat_url:
                            # Mostrar el enlace para que el usuario lo copie o abra
                            st.markdown(f"""
                            <div style="
                                background: linear-gradient(135deg, #2d2d2d 0%, #1a1a1a 100%);
                                padding: 20px;
                                border-radius: 15px;
                                margin: 15px 0;
                                border-left: 4px solid #667eea;
                            ">
                                <p style="color: #d0d0d0; margin: 0 0 10px 0;">
                                    🔗 <strong style="color: #e0e0e0;">Enlace del recurso:</strong>
                                </p>
                                <p style="
                                    color: #58a6ff;
                                    margin: 0;
                                    word-break: break-all;
                                    font-family: monospace;
                                    background: #1e1e1e;
                                    padding: 10px;
                                    border-radius: 8px;
                                ">
                                    {mat_url}
                                </p>
                                <p style="color: #b0b0b0; margin: 10px 0 0 0; font-size: 0.9em;">
                                    💡 Copia este enlace y ábrelo en una nueva pestaña de tu navegador
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Botón para copiar al portapapeles
                            if st.button(f"📋 Copiar Enlace", key=f"copy_url_{mat_id}", use_container_width=True):
                                st.code(mat_url, language=None)
                                st.info("✅ Enlace mostrado arriba - Cópialo manualmente (Ctrl+C)")
                        else:
                            # URL no válida o de ejemplo
                            st.info("🔍 Este recurso aún no tiene un enlace específico. Puedes buscar información sobre este tema en tu buscador favorito.")
                    
                    # Botón individual para marcar como leído
                    if not is_completed:
                        if st.button(f"✅ Marcar como Leído", key=f"mark_mat_{mat_id}", use_container_width=True):
                            conn.execute("""
                                UPDATE ai_course_materials 
                                SET is_completed = 1, completed_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            """, (mat_id,))
                            conn.commit()
                            st.success("✅ Material marcado")
                            st.rerun()
                    else:
                        st.success("✅ Ya leíste este material")
    
    with tab2:
        # Recursos externos recomendados basados en lenguaje y nivel
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 20px;
            text-align: center;
        ">
            <h3 style="color: white; margin: 0 0 10px 0;">🌐 Recursos Externos Curados</h3>
            <p style="color: rgba(255,255,255,0.9); margin: 0;">
                Páginas web, documentación oficial y plataformas recomendadas para aprender más
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Diccionario de recursos por lenguaje y nivel
        external_resources = {
            'Python': {
                'principiante': [
                    {
                        'title': '📘 Documentación Oficial de Python',
                        'url': 'https://docs.python.org/es/3/tutorial/',
                        'description': 'Tutorial oficial de Python en español, perfecto para principiantes',
                        'type': 'documentation'
                    },
                    {
                        'title': '🎓 Python para Todos (py4e.com)',
                        'url': 'https://es.py4e.com/',
                        'description': 'Curso gratuito completo de Python para principiantes',
                        'type': 'website'
                    },
                    {
                        'title': '💻 W3Schools Python Tutorial',
                        'url': 'https://www.w3schools.com/python/',
                        'description': 'Tutoriales interactivos con ejemplos prácticos',
                        'type': 'website'
                    },
                    {
                        'title': '📚 Real Python - Beginner',
                        'url': 'https://realpython.com/tutorials/basics/',
                        'description': 'Tutoriales de calidad para fundamentos de Python',
                        'type': 'website'
                    }
                ],
                'intermedio': [
                    {
                        'title': '📘 Python Documentation',
                        'url': 'https://docs.python.org/3/',
                        'description': 'Documentación completa de Python con guías avanzadas',
                        'type': 'documentation'
                    },
                    {
                        'title': '🎯 Real Python - Intermediate',
                        'url': 'https://realpython.com/tutorials/intermediate/',
                        'description': 'Tutoriales de nivel intermedio sobre temas específicos',
                        'type': 'website'
                    },
                    {
                        'title': '💡 Python Tips',
                        'url': 'https://book.pythontips.com/',
                        'description': 'Libro gratuito con tips y trucos de Python',
                        'type': 'website'
                    },
                    {
                        'title': '🔧 Python Module of the Week',
                        'url': 'https://pymotw.com/3/',
                        'description': 'Guía detallada de módulos de la biblioteca estándar',
                        'type': 'documentation'
                    }
                ],
                'avanzado': [
                    {
                        'title': '📘 Python Enhancement Proposals (PEPs)',
                        'url': 'https://peps.python.org/',
                        'description': 'Propuestas y especificaciones técnicas de Python',
                        'type': 'documentation'
                    },
                    {
                        'title': '🎯 Real Python - Advanced',
                        'url': 'https://realpython.com/tutorials/advanced/',
                        'description': 'Tutoriales avanzados sobre arquitectura y optimización',
                        'type': 'website'
                    },
                    {
                        'title': '⚡ Python Speed',
                        'url': 'https://pythonspeed.com/',
                        'description': 'Optimización y mejores prácticas de rendimiento',
                        'type': 'website'
                    },
                    {
                        'title': '🔬 Python Patterns',
                        'url': 'https://python-patterns.guide/',
                        'description': 'Patrones de diseño y arquitectura en Python',
                        'type': 'website'
                    }
                ]
            },
            'JavaScript': {
                'principiante': [
                    {
                        'title': '📘 MDN Web Docs - JavaScript',
                        'url': 'https://developer.mozilla.org/es/docs/Web/JavaScript/Guide',
                        'description': 'Guía oficial de JavaScript por Mozilla',
                        'type': 'documentation'
                    },
                    {
                        'title': '🎓 JavaScript.info',
                        'url': 'https://javascript.info/',
                        'description': 'Tutorial moderno de JavaScript desde cero',
                        'type': 'website'
                    },
                    {
                        'title': '💻 W3Schools JavaScript',
                        'url': 'https://www.w3schools.com/js/',
                        'description': 'Tutoriales interactivos con ejemplos',
                        'type': 'website'
                    },
                    {
                        'title': '📚 freeCodeCamp JavaScript',
                        'url': 'https://www.freecodecamp.org/learn/javascript-algorithms-and-data-structures/',
                        'description': 'Curso gratuito con certificación',
                        'type': 'website'
                    }
                ],
                'intermedio': [
                    {
                        'title': '📘 MDN JavaScript Reference',
                        'url': 'https://developer.mozilla.org/es/docs/Web/JavaScript/Reference',
                        'description': 'Referencia completa de JavaScript',
                        'type': 'documentation'
                    },
                    {
                        'title': '🎯 JavaScript.info - Advanced',
                        'url': 'https://javascript.info/advanced-functions',
                        'description': 'Conceptos avanzados de funciones y closures',
                        'type': 'website'
                    },
                    {
                        'title': '💡 Eloquent JavaScript',
                        'url': 'https://eloquentjavascript.net/',
                        'description': 'Libro gratuito sobre JavaScript moderno',
                        'type': 'website'
                    },
                    {
                        'title': '🔧 You Don\'t Know JS',
                        'url': 'https://github.com/getify/You-Dont-Know-JS',
                        'description': 'Serie de libros profundos sobre JavaScript',
                        'type': 'website'
                    }
                ],
                'avanzado': [
                    {
                        'title': '📘 ECMAScript Specifications',
                        'url': 'https://tc39.es/ecma262/',
                        'description': 'Especificación oficial del lenguaje',
                        'type': 'documentation'
                    },
                    {
                        'title': '🎯 JavaScript Weekly',
                        'url': 'https://javascriptweekly.com/',
                        'description': 'Newsletter con las últimas novedades',
                        'type': 'website'
                    },
                    {
                        'title': '⚡ V8 Blog',
                        'url': 'https://v8.dev/blog',
                        'description': 'Blog oficial del motor V8 de JavaScript',
                        'type': 'website'
                    },
                    {
                        'title': '🔬 JavaScript Patterns',
                        'url': 'https://www.patterns.dev/',
                        'description': 'Patrones de diseño modernos en JavaScript',
                        'type': 'website'
                    }
                ]
            },
            'Java': {
                'principiante': [
                    {'title': '📘 Oracle Java Tutorials', 'url': 'https://docs.oracle.com/javase/tutorial/', 'description': 'Tutoriales oficiales de Oracle para aprender Java', 'type': 'documentation'},
                    {'title': '🎓 W3Schools Java', 'url': 'https://www.w3schools.com/java/', 'description': 'Tutoriales interactivos de Java para principiantes', 'type': 'website'},
                    {'title': '💻 Java Programming MOOC', 'url': 'https://java-programming.mooc.fi/', 'description': 'Curso gratuito completo de Java de la Universidad de Helsinki', 'type': 'website'},
                    {'title': '📚 Learn Java Online', 'url': 'https://www.learnjavaonline.org/', 'description': 'Plataforma interactiva para aprender Java', 'type': 'website'}
                ],
                'intermedio': [
                    {'title': '📘 Java SE Documentation', 'url': 'https://docs.oracle.com/en/java/javase/', 'description': 'Documentación completa de Java SE', 'type': 'documentation'},
                    {'title': '🎯 Baeldung', 'url': 'https://www.baeldung.com/', 'description': 'Tutoriales avanzados y guías de Java', 'type': 'website'},
                    {'title': '💡 Java Design Patterns', 'url': 'https://java-design-patterns.com/', 'description': 'Patrones de diseño implementados en Java', 'type': 'website'},
                    {'title': '🔧 JournalDev', 'url': 'https://www.journaldev.com/java', 'description': 'Tutoriales y ejemplos de Java', 'type': 'website'}
                ],
                'avanzado': [
                    {'title': '📘 Java Language Specification', 'url': 'https://docs.oracle.com/javase/specs/', 'description': 'Especificación oficial del lenguaje Java', 'type': 'documentation'},
                    {'title': '🎯 Inside Java', 'url': 'https://inside.java/', 'description': 'Blog oficial del equipo de Java en Oracle', 'type': 'website'},
                    {'title': '⚡ Java Performance Tuning', 'url': 'https://www.baeldung.com/java-performance', 'description': 'Guías de optimización de rendimiento', 'type': 'website'},
                    {'title': '🔬 Effective Java', 'url': 'https://www.oreilly.com/library/view/effective-java/9780134686097/', 'description': 'Mejores prácticas de programación en Java', 'type': 'website'}
                ]
            },
            'C++': {
                'principiante': [
                    {'title': '📘 cplusplus.com Tutorial', 'url': 'https://cplusplus.com/doc/tutorial/', 'description': 'Tutorial completo de C++ para principiantes', 'type': 'documentation'},
                    {'title': '🎓 LearnCpp.com', 'url': 'https://www.learncpp.com/', 'description': 'Curso gratuito y completo de C++', 'type': 'website'},
                    {'title': '💻 W3Schools C++', 'url': 'https://www.w3schools.com/cpp/', 'description': 'Tutoriales interactivos de C++', 'type': 'website'},
                    {'title': '📚 C++ Reference', 'url': 'https://en.cppreference.com/', 'description': 'Referencia completa del lenguaje C++', 'type': 'documentation'}
                ],
                'intermedio': [
                    {'title': '📘 C++ Core Guidelines', 'url': 'https://isocpp.github.io/CppCoreGuidelines/', 'description': 'Guías oficiales de mejores prácticas en C++', 'type': 'documentation'},
                    {'title': '🎯 Modern C++ Features', 'url': 'https://github.com/AnthonyCalandra/modern-cpp-features', 'description': 'Características modernas de C++ (C++11/14/17/20)', 'type': 'website'},
                    {'title': '💡 GeeksforGeeks C++', 'url': 'https://www.geeksforgeeks.org/c-plus-plus/', 'description': 'Tutoriales y ejemplos de C++', 'type': 'website'},
                    {'title': '🔧 C++ Patterns', 'url': 'https://cpppatterns.com/', 'description': 'Patrones y técnicas comunes en C++', 'type': 'website'}
                ],
                'avanzado': [
                    {'title': '📘 ISO C++ Standard', 'url': 'https://isocpp.org/std/the-standard', 'description': 'Estándar oficial del lenguaje C++', 'type': 'documentation'},
                    {'title': '🎯 C++ Weekly', 'url': 'https://www.youtube.com/c/lefticus1', 'description': 'Videos semanales sobre C++ moderno', 'type': 'website'},
                    {'title': '⚡ Optimization Guide', 'url': 'https://www.agner.org/optimize/', 'description': 'Guías de optimización de C++', 'type': 'documentation'},
                    {'title': '🔬 Awesome C++', 'url': 'https://github.com/fffaraz/awesome-cpp', 'description': 'Lista curada de recursos y bibliotecas de C++', 'type': 'website'}
                ]
            },
            'C#': {
                'principiante': [
                    {'title': '📘 Microsoft C# Docs', 'url': 'https://learn.microsoft.com/es-es/dotnet/csharp/', 'description': 'Documentación oficial de C# por Microsoft', 'type': 'documentation'},
                    {'title': '🎓 C# Tutorial', 'url': 'https://www.w3schools.com/cs/', 'description': 'Tutoriales interactivos de C#', 'type': 'website'},
                    {'title': '💻 Learn C#', 'url': 'https://dotnet.microsoft.com/learn/csharp', 'description': 'Recursos oficiales para aprender C#', 'type': 'website'},
                    {'title': '📚 C# Station', 'url': 'https://csharp-station.com/', 'description': 'Tutoriales y recursos de C#', 'type': 'website'}
                ],
                'intermedio': [
                    {'title': '📘 .NET Documentation', 'url': 'https://learn.microsoft.com/es-es/dotnet/', 'description': 'Documentación completa de .NET y C#', 'type': 'documentation'},
                    {'title': '🎯 C# Corner', 'url': 'https://www.c-sharpcorner.com/', 'description': 'Comunidad y tutoriales de C#', 'type': 'website'},
                    {'title': '💡 Pluralsight C#', 'url': 'https://www.pluralsight.com/paths/csharp', 'description': 'Cursos profesionales de C#', 'type': 'website'},
                    {'title': '🔧 C# Design Patterns', 'url': 'https://refactoring.guru/design-patterns/csharp', 'description': 'Patrones de diseño en C#', 'type': 'website'}
                ],
                'avanzado': [
                    {'title': '📘 C# Language Specification', 'url': 'https://learn.microsoft.com/es-es/dotnet/csharp/language-reference/language-specification/', 'description': 'Especificación oficial del lenguaje C#', 'type': 'documentation'},
                    {'title': '🎯 .NET Blog', 'url': 'https://devblogs.microsoft.com/dotnet/', 'description': 'Blog oficial del equipo de .NET', 'type': 'website'},
                    {'title': '⚡ Performance Tips', 'url': 'https://learn.microsoft.com/es-es/dotnet/csharp/advanced-topics/performance/', 'description': 'Optimización de rendimiento en C#', 'type': 'documentation'},
                    {'title': '🔬 Awesome .NET', 'url': 'https://github.com/quozd/awesome-dotnet', 'description': 'Recursos y bibliotecas de .NET', 'type': 'website'}
                ]
            },
            'Ruby': {
                'principiante': [
                    {'title': '📘 Ruby Documentation', 'url': 'https://www.ruby-lang.org/es/documentation/', 'description': 'Documentación oficial de Ruby', 'type': 'documentation'},
                    {'title': '🎓 Ruby in 20 Minutes', 'url': 'https://www.ruby-lang.org/es/documentation/quickstart/', 'description': 'Introducción rápida a Ruby', 'type': 'website'},
                    {'title': '💻 Learn Ruby', 'url': 'https://www.learnrubyonline.org/', 'description': 'Tutoriales interactivos de Ruby', 'type': 'website'},
                    {'title': '📚 Ruby Monk', 'url': 'https://rubymonk.com/', 'description': 'Curso interactivo gratuito de Ruby', 'type': 'website'}
                ],
                'intermedio': [
                    {'title': '📘 Ruby API', 'url': 'https://ruby-doc.org/', 'description': 'Documentación completa de la API de Ruby', 'type': 'documentation'},
                    {'title': '🎯 Ruby Guides', 'url': 'https://www.rubyguides.com/', 'description': 'Guías y tutoriales de Ruby', 'type': 'website'},
                    {'title': '💡 Ruby Weekly', 'url': 'https://rubyweekly.com/', 'description': 'Newsletter semanal de Ruby', 'type': 'website'},
                    {'title': '🔧 Ruby Tapas', 'url': 'https://www.rubytapas.com/', 'description': 'Videos cortos sobre técnicas de Ruby', 'type': 'website'}
                ],
                'avanzado': [
                    {'title': '📘 Ruby Core', 'url': 'https://ruby-doc.org/core/', 'description': 'Documentación del núcleo de Ruby', 'type': 'documentation'},
                    {'title': '🎯 Ruby Inside', 'url': 'http://www.rubyinside.com/', 'description': 'Noticias y artículos avanzados de Ruby', 'type': 'website'},
                    {'title': '⚡ Ruby Performance', 'url': 'https://github.com/JuanitoFatas/fast-ruby', 'description': 'Guía de optimización de Ruby', 'type': 'website'},
                    {'title': '🔬 Awesome Ruby', 'url': 'https://github.com/markets/awesome-ruby', 'description': 'Lista curada de recursos de Ruby', 'type': 'website'}
                ]
            },
            'PHP': {
                'principiante': [
                    {'title': '📘 PHP Manual', 'url': 'https://www.php.net/manual/es/', 'description': 'Manual oficial de PHP en español', 'type': 'documentation'},
                    {'title': '🎓 W3Schools PHP', 'url': 'https://www.w3schools.com/php/', 'description': 'Tutoriales interactivos de PHP', 'type': 'website'},
                    {'title': '💻 Learn PHP', 'url': 'https://www.learn-php.org/', 'description': 'Tutoriales interactivos gratuitos', 'type': 'website'},
                    {'title': '📚 PHP The Right Way', 'url': 'https://phptherightway.com/', 'description': 'Mejores prácticas de PHP moderno', 'type': 'website'}
                ],
                'intermedio': [
                    {'title': '📘 PHP Documentation', 'url': 'https://www.php.net/docs.php', 'description': 'Documentación completa de PHP', 'type': 'documentation'},
                    {'title': '🎯 PHP.Watch', 'url': 'https://php.watch/', 'description': 'Noticias y cambios en PHP', 'type': 'website'},
                    {'title': '💡 Laracasts', 'url': 'https://laracasts.com/', 'description': 'Videos y tutoriales de PHP y Laravel', 'type': 'website'},
                    {'title': '🔧 PHP Design Patterns', 'url': 'https://refactoring.guru/design-patterns/php', 'description': 'Patrones de diseño en PHP', 'type': 'website'}
                ],
                'avanzado': [
                    {'title': '📘 PHP Internals', 'url': 'https://www.phpinternalsbook.com/', 'description': 'Funcionamiento interno de PHP', 'type': 'documentation'},
                    {'title': '🎯 PHP Weekly', 'url': 'https://www.phpweekly.com/', 'description': 'Newsletter semanal de PHP', 'type': 'website'},
                    {'title': '⚡ PHP Performance', 'url': 'https://www.php.net/manual/es/features.gc.performance-considerations.php', 'description': 'Optimización de rendimiento', 'type': 'documentation'},
                    {'title': '🔬 Awesome PHP', 'url': 'https://github.com/ziadoz/awesome-php', 'description': 'Lista curada de recursos de PHP', 'type': 'website'}
                ]
            },
            'Go': {
                'principiante': [
                    {'title': '📘 Go Tour', 'url': 'https://go.dev/tour/', 'description': 'Tour interactivo oficial de Go', 'type': 'documentation'},
                    {'title': '🎓 Go by Example', 'url': 'https://gobyexample.com/', 'description': 'Aprende Go con ejemplos prácticos', 'type': 'website'},
                    {'title': '💻 Learn Go', 'url': 'https://www.learn-golang.org/', 'description': 'Tutoriales interactivos de Go', 'type': 'website'},
                    {'title': '📚 Go Documentation', 'url': 'https://go.dev/doc/', 'description': 'Documentación oficial de Go', 'type': 'documentation'}
                ],
                'intermedio': [
                    {'title': '📘 Effective Go', 'url': 'https://go.dev/doc/effective_go', 'description': 'Guía oficial de mejores prácticas', 'type': 'documentation'},
                    {'title': '🎯 Go Blog', 'url': 'https://go.dev/blog/', 'description': 'Blog oficial del equipo de Go', 'type': 'website'},
                    {'title': '💡 Gophercises', 'url': 'https://gophercises.com/', 'description': 'Ejercicios prácticos de Go', 'type': 'website'},
                    {'title': '🔧 Go Patterns', 'url': 'https://github.com/tmrts/go-patterns', 'description': 'Patrones de diseño en Go', 'type': 'website'}
                ],
                'avanzado': [
                    {'title': '📘 Go Specification', 'url': 'https://go.dev/ref/spec', 'description': 'Especificación oficial del lenguaje', 'type': 'documentation'},
                    {'title': '🎯 Go Weekly', 'url': 'https://golangweekly.com/', 'description': 'Newsletter semanal de Go', 'type': 'website'},
                    {'title': '⚡ High Performance Go', 'url': 'https://dave.cheney.net/high-performance-go-workshop/gopherchina-2019.html', 'description': 'Workshop de optimización', 'type': 'website'},
                    {'title': '🔬 Awesome Go', 'url': 'https://github.com/avelino/awesome-go', 'description': 'Lista curada de recursos de Go', 'type': 'website'}
                ]
            },
            'Rust': {
                'principiante': [
                    {'title': '📘 The Rust Book', 'url': 'https://doc.rust-lang.org/book/', 'description': 'Libro oficial de Rust para principiantes', 'type': 'documentation'},
                    {'title': '🎓 Rust by Example', 'url': 'https://doc.rust-lang.org/rust-by-example/', 'description': 'Aprende Rust con ejemplos', 'type': 'documentation'},
                    {'title': '💻 Rustlings', 'url': 'https://github.com/rust-lang/rustlings', 'description': 'Ejercicios pequeños para aprender Rust', 'type': 'website'},
                    {'title': '📚 Learn Rust', 'url': 'https://www.rust-lang.org/learn', 'description': 'Recursos oficiales para aprender Rust', 'type': 'website'}
                ],
                'intermedio': [
                    {'title': '📘 Rust Standard Library', 'url': 'https://doc.rust-lang.org/std/', 'description': 'Documentación de la biblioteca estándar', 'type': 'documentation'},
                    {'title': '🎯 Rust Blog', 'url': 'https://blog.rust-lang.org/', 'description': 'Blog oficial del equipo de Rust', 'type': 'website'},
                    {'title': '💡 Rust Cookbook', 'url': 'https://rust-lang-nursery.github.io/rust-cookbook/', 'description': 'Recetas y patrones comunes', 'type': 'documentation'},
                    {'title': '🔧 Rust Patterns', 'url': 'https://rust-unofficial.github.io/patterns/', 'description': 'Patrones de diseño en Rust', 'type': 'website'}
                ],
                'avanzado': [
                    {'title': '📘 The Rustonomicon', 'url': 'https://doc.rust-lang.org/nomicon/', 'description': 'Guía de Rust unsafe y avanzado', 'type': 'documentation'},
                    {'title': '🎯 This Week in Rust', 'url': 'https://this-week-in-rust.org/', 'description': 'Newsletter semanal de Rust', 'type': 'website'},
                    {'title': '⚡ Rust Performance Book', 'url': 'https://nnethercote.github.io/perf-book/', 'description': 'Guía de optimización de rendimiento', 'type': 'documentation'},
                    {'title': '🔬 Awesome Rust', 'url': 'https://github.com/rust-unofficial/awesome-rust', 'description': 'Lista curada de recursos de Rust', 'type': 'website'}
                ]
            },
            'TypeScript': {
                'principiante': [
                    {'title': '📘 TypeScript Handbook', 'url': 'https://www.typescriptlang.org/docs/handbook/intro.html', 'description': 'Manual oficial de TypeScript', 'type': 'documentation'},
                    {'title': '🎓 TypeScript Tutorial', 'url': 'https://www.typescripttutorial.net/', 'description': 'Tutorial completo de TypeScript', 'type': 'website'},
                    {'title': '💻 Learn TypeScript', 'url': 'https://www.learn-ts.org/', 'description': 'Tutoriales interactivos', 'type': 'website'},
                    {'title': '📚 TypeScript Deep Dive', 'url': 'https://basarat.gitbook.io/typescript/', 'description': 'Libro gratuito sobre TypeScript', 'type': 'website'}
                ],
                'intermedio': [
                    {'title': '📘 TypeScript Reference', 'url': 'https://www.typescriptlang.org/docs/', 'description': 'Documentación completa de TypeScript', 'type': 'documentation'},
                    {'title': '🎯 TypeScript Blog', 'url': 'https://devblogs.microsoft.com/typescript/', 'description': 'Blog oficial de TypeScript', 'type': 'website'},
                    {'title': '💡 Type Challenges', 'url': 'https://github.com/type-challenges/type-challenges', 'description': 'Desafíos del sistema de tipos', 'type': 'website'},
                    {'title': '🔧 TypeScript Patterns', 'url': 'https://refactoring.guru/design-patterns/typescript', 'description': 'Patrones de diseño en TypeScript', 'type': 'website'}
                ],
                'avanzado': [
                    {'title': '📘 TypeScript Compiler API', 'url': 'https://github.com/microsoft/TypeScript/wiki/Using-the-Compiler-API', 'description': 'API del compilador de TypeScript', 'type': 'documentation'},
                    {'title': '🎯 TypeScript Weekly', 'url': 'https://typescript-weekly.com/', 'description': 'Newsletter semanal de TypeScript', 'type': 'website'},
                    {'title': '⚡ Performance Tips', 'url': 'https://github.com/microsoft/TypeScript/wiki/Performance', 'description': 'Optimización de TypeScript', 'type': 'documentation'},
                    {'title': '🔬 Awesome TypeScript', 'url': 'https://github.com/dzharii/awesome-typescript', 'description': 'Lista curada de recursos', 'type': 'website'}
                ]
            },
            'SQL': {
                'principiante': [
                    {'title': '📘 W3Schools SQL', 'url': 'https://www.w3schools.com/sql/', 'description': 'Tutorial interactivo de SQL', 'type': 'website'},
                    {'title': '🎓 SQLBolt', 'url': 'https://sqlbolt.com/', 'description': 'Lecciones interactivas de SQL', 'type': 'website'},
                    {'title': '💻 Learn SQL', 'url': 'https://www.codecademy.com/learn/learn-sql', 'description': 'Curso interactivo de SQL', 'type': 'website'},
                    {'title': '📚 SQL Tutorial', 'url': 'https://www.sqltutorial.org/', 'description': 'Tutorial completo de SQL', 'type': 'website'}
                ],
                'intermedio': [
                    {'title': '📘 PostgreSQL Docs', 'url': 'https://www.postgresql.org/docs/', 'description': 'Documentación de PostgreSQL', 'type': 'documentation'},
                    {'title': '🎯 MySQL Tutorial', 'url': 'https://dev.mysql.com/doc/', 'description': 'Documentación oficial de MySQL', 'type': 'documentation'},
                    {'title': '💡 SQL Server Docs', 'url': 'https://learn.microsoft.com/es-es/sql/', 'description': 'Documentación de SQL Server', 'type': 'documentation'},
                    {'title': '🔧 Mode SQL Tutorial', 'url': 'https://mode.com/sql-tutorial/', 'description': 'Tutorial avanzado de SQL', 'type': 'website'}
                ],
                'avanzado': [
                    {'title': '📘 SQL Performance', 'url': 'https://use-the-index-luke.com/', 'description': 'Guía de optimización de SQL', 'type': 'website'},
                    {'title': '🎯 Database Design', 'url': 'https://www.databasestar.com/', 'description': 'Diseño y modelado de bases de datos', 'type': 'website'},
                    {'title': '⚡ Query Optimization', 'url': 'https://www.postgresql.org/docs/current/performance-tips.html', 'description': 'Optimización de consultas', 'type': 'documentation'},
                    {'title': '🔬 SQL Antipatterns', 'url': 'https://pragprog.com/titles/bksqla/sql-antipatterns/', 'description': 'Antipatrones y soluciones en SQL', 'type': 'website'}
                ]
            }
        }
        
        # Obtener recursos para el lenguaje y nivel actual
        language = ai_course.get('language', 'Python')
        level = ai_course.get('level', 'principiante')
        
        resources = external_resources.get(language, {}).get(level, [])
        
        if not resources:
            st.info(f"📭 Recursos para {language} - {level} estarán disponibles pronto")
        else:
            for resource in resources:
                icon = '📄' if resource['type'] == 'documentation' else '🌐'
                gradient = 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)' if resource['type'] == 'documentation' else 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)'
                
                with st.expander(f"{icon} {resource['title']}", expanded=False):
                    st.markdown(f"""
                    <div style="
                        background: {gradient};
                        padding: 20px;
                        border-radius: 15px;
                        margin-bottom: 15px;
                    ">
                        <p style="color: rgba(255, 255, 255, 0.95); margin: 0 0 15px 0; font-size: 1.05em; line-height: 1.5;">
                            {resource['description']}
                        </p>
                        <div style="
                            background: rgba(255, 255, 255, 0.2);
                            padding: 15px;
                            border-radius: 10px;
                            margin-top: 10px;
                        ">
                            <p style="color: white; margin: 0 0 10px 0; font-weight: bold;">
                                🔗 Enlace:
                            </p>
                            <p style="
                                color: white;
                                margin: 0;
                                word-break: break-all;
                                font-family: monospace;
                                font-size: 0.9em;
                            ">
                                {resource['url']}
                            </p>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.link_button("🌐 Abrir Recurso", resource['url'], use_container_width=True)
                    with col2:
                        if st.button(f"📋 Copiar URL", key=f"copy_external_{section_id}_{resource['title']}", use_container_width=True):
                            st.code(resource['url'], language=None)
                            st.success("✅ URL lista para copiar")
    
    # Botón para marcar la sección como completada
    st.markdown("---")
    
    # Verificar si la sección ya está completada
    is_section_completed = section.get('is_completed', 0)
    
    # Obtener el ID del curso desde la sección
    ai_course_id = section.get('ai_course_id')
    if not ai_course_id and isinstance(ai_course, dict):
        ai_course_id = ai_course.get('id')
    
    if not is_section_completed:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 15px;
            margin: 20px 0;
            text-align: center;
        ">
            <h3 style="color: white; margin: 0 0 10px 0;">✅ ¿Terminaste de estudiar esta sección?</h3>
            <p style="color: rgba(255,255,255,0.9); margin: 0;">
                Marca esta sección como completada para actualizar tu progreso
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("✅ Marcar Sección como Completada", key=f"complete_section_{section_id}", type="primary", use_container_width=True):
            try:
                # Marcar sección como completada
                conn.execute("""
                    UPDATE ai_course_topics 
                    SET is_completed = 1
                    WHERE id = ?
                """, (section_id,))
                
                # Actualizar progreso del curso
                if ai_course_id:
                    total_sections = conn.execute("""
                        SELECT COUNT(*) FROM ai_course_topics 
                        WHERE ai_course_id = ?
                    """, (ai_course_id,)).fetchone()[0]
                    
                    completed_sections = conn.execute("""
                        SELECT COUNT(*) FROM ai_course_topics 
                        WHERE ai_course_id = ? AND is_completed = 1
                    """, (ai_course_id,)).fetchone()[0]
                    
                    progress = (completed_sections / total_sections) * 100 if total_sections > 0 else 0
                    
                    conn.execute("""
                        UPDATE ai_courses 
                        SET progress_percentage = ?
                        WHERE id = ?
                    """, (progress, ai_course_id))
                
                conn.commit()
                st.success("🎉 ¡Sección completada! Tu progreso ha sido actualizado")
                st.balloons()
                # Limpiar caché para que se actualicen las consultas
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error al completar sección: {str(e)}")
    else:
        st.success("✅ Ya completaste esta sección")
        if st.button("🔄 Marcar como No Completada", key=f"uncomplete_section_{section_id}", use_container_width=True):
            try:
                conn.execute("""
                    UPDATE ai_course_topics 
                    SET is_completed = 0
                    WHERE id = ?
                """, (section_id,))
                
                # Actualizar progreso del curso
                if ai_course_id:
                    total_sections = conn.execute("""
                        SELECT COUNT(*) FROM ai_course_topics 
                        WHERE ai_course_id = ?
                    """, (ai_course_id,)).fetchone()[0]
                    
                    completed_sections = conn.execute("""
                        SELECT COUNT(*) FROM ai_course_topics 
                        WHERE ai_course_id = ? AND is_completed = 1
                    """, (ai_course_id,)).fetchone()[0]
                    
                    progress = (completed_sections / total_sections) * 100 if total_sections > 0 else 0
                    
                    conn.execute("""
                        UPDATE ai_courses 
                        SET progress_percentage = ?
                        WHERE id = ?
                    """, (progress, ai_course_id))
                
                conn.commit()
                st.info("Sección marcada como no completada")
                # Limpiar caché para que se actualicen las consultas
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error al descompletar sección: {str(e)}")



def render_section_exercise(conn, user, model, section, ai_course, sections_rows):
    """Renderiza el ejercicio usando el banco de preguntas pregeneradas"""
    
    section_id = section['id']
    section_number = section['topic_number']
    
    # Verificar contenido leído
    content_read = conn.execute("""
        SELECT is_completed FROM ai_course_materials 
        WHERE topic_id = ? AND is_completed = 1
        LIMIT 1
    """, (section_id,)).fetchone()
    
    if not content_read:
        st.warning("⚠️ Primero marca el contenido como leído")
        return
    
    # Usar IA para generar evaluación creativa
    from utils_ai import generate_creative_section_evaluation
    
    # CRÍTICO: Guardar preguntas en session_state para que no cambien en cada recarga
    questions_session_key = f"questions_ai_{section_id}_{ai_course['language']}_{ai_course['level']}"
    
    if questions_session_key not in st.session_state:
        # Primera vez: generar con IA y guardar preguntas
        with st.spinner(f"🤖 Generando evaluación creativa para {section['title']}..."):
            evaluation_data = generate_creative_section_evaluation(
                model=model,
                language=ai_course['language'],
                level=ai_course['level'],
                section_title=section['title'],
                num_questions=15
            )
            
            if not evaluation_data.get('questions'):
                st.error("❌ Error generando evaluación")
                return
            
            st.session_state[questions_session_key] = evaluation_data['questions']
            st.success(f"✅ Evaluación generada: {len(evaluation_data['questions'])} preguntas únicas")
    
    # Usar preguntas guardadas en session_state
    questions_list = st.session_state[questions_session_key]
    
    # Convertir las preguntas al formato esperado
    import json
    formatted_questions = []
    for idx, q in enumerate(questions_list):
        formatted_questions.append({
            'id': idx,
            'question': q['question'],
            'options': q['options'],
            'correct_index': q['correct_answer'],
            'explanation': q['explanation'],
            'points': 20,
            'difficulty': 1,
            'topic_area': 'general',
            'code_example': q['example_code']
        })
    
    questions_list = formatted_questions
    
    # Ahora tenemos questions_list con las preguntas del banco
    if not questions_list:
        st.warning("⚠️ No se encontraron preguntas")
        return
    
    # Inicializar índice de pregunta actual en session_state
    session_key = f"current_question_topic_{section_id}"
    if session_key not in st.session_state:
        st.session_state[session_key] = 0
    
    current_question_index = st.session_state[session_key]
    
    # Asegurar que el índice esté dentro del rango
    if current_question_index >= len(questions_list):
        current_question_index = 0
        st.session_state[session_key] = 0
    
    # Obtener pregunta actual
    question_data = questions_list[current_question_index]
    
    # Botón para obtener nuevas preguntas aleatorias del banco
    if st.button("🔄 Obtener Nuevas Preguntas", key=f"regen_ex_{section_id}", help="Selecciona 15 preguntas aleatorias diferentes del banco"):
        # Limpiar las preguntas guardadas en session_state para forzar regeneración
        if questions_session_key in st.session_state:
            del st.session_state[questions_session_key]
        st.rerun()
    
    # Mostrar ejercicio con la pregunta
    if question_data and questions_list:
        # Mostrar progreso
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 25px;
            border-radius: 20px;
            margin-bottom: 25px;
        ">
            <h2 style="color: white; margin: 0 0 15px 0;">
                🎯 Evaluación: {fix_language_in_text(section['title'], ai_course['language'])}
            </h2>
            <div style="color: rgba(255, 255, 255, 0.95); line-height: 1.6;">
                Responde las siguientes preguntas sobre {section['title']} en {ai_course['language']}. Todas las preguntas incluyen código.
            </div>
            <div style="margin-top: 15px; padding: 10px; background: rgba(255,255,255,0.2); border-radius: 10px;">
                <span style="color: white; font-weight: bold;">Pregunta {current_question_index + 1} de {len(questions_list)}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # INSTRUCCIONES DETALLADAS (MOVIDAS AQUÍ ARRIBA)
        with st.container():
            st.markdown("""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 25px; border-radius: 20px; margin-bottom: 25px; border-left: 6px solid #4c51bf; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <h3 style="color: #ffffff; margin: 0 0 15px 0;">📋 Instrucciones</h3>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("**Qué debes hacer:**")
            st.markdown(f"""
            1. Lee cuidadosamente el código presentado
            2. Analiza qué hace el código o qué concepto aplica
            3. Selecciona la respuesta correcta de las opciones
            4. Haz clic en "Verificar Respuesta" cuando estés seguro
            """)
            
            st.markdown("**Requisitos:**")
            st.markdown(f"""
            - Responder correctamente al menos 10 de 15 preguntas (nota ≥6)
            - Necesitas nota ≥6 para desbloquear la siguiente sección
            """)
            
            st.markdown(f"**Nivel:** {ai_course['level'].title()} - Adaptado a tu nivel")
            
            # Mostrar hints específicos de la pregunta si existen
            if question_data.get('explanation'):
                with st.expander("💡 Ver Pistas"):
                    # Generar una pista específica basada en la pregunta
                    hint_text = f"Analiza cuidadosamente el código presentado. "
                    
                    # Agregar pista específica según el tipo de pregunta
                    question_text = question_data.get('question', '').lower()
                    if 'imprime' in question_text or 'print' in question_text or 'console.log' in question_text:
                        hint_text += "Piensa en qué valor se imprimirá en la consola al ejecutar este código. "
                    elif 'resultado' in question_text or 'retorna' in question_text or 'devuelve' in question_text:
                        hint_text += "Considera qué valor retorna o produce el código al final de su ejecución. "
                    elif 'error' in question_text:
                        hint_text += "Revisa si hay algún error de sintaxis o lógica en el código. "
                    elif 'tipo' in question_text or 'type' in question_text:
                        hint_text += "Identifica el tipo de dato que se está utilizando o retornando. "
                    else:
                        hint_text += "Ejecuta mentalmente el código línea por línea para entender su comportamiento. "
                    
                    hint_text += f"\n\n💡 Recuerda los conceptos de {section['title']} que estudiaste en la lección."
                    
                    st.info(hint_text)
            
            st.markdown("---")
        
        # Mostrar la pregunta con el código
        question_text = question_data.get('question', '')
        code_in_question = None
        question_without_code = question_text
        
        # Buscar código en formato markdown
        import re
        code_block_pattern = r'```[\w]*\n(.*?)\n```'
        match = re.search(code_block_pattern, question_text, re.DOTALL)
        if match:
            code_in_question = match.group(1)
            # Remover el código del texto de la pregunta para mostrarlo por separado
            question_without_code = re.sub(code_block_pattern, '', question_text, flags=re.DOTALL).strip()
        
        st.markdown(f"""
        <div style="
            background: rgba(30, 30, 30, 0.95);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 20px;
            border-left: 4px solid #667eea;
        ">
            <h3 style="color: #667eea; margin: 0 0 15px 0;">📝 Pregunta {current_question_index + 1}</h3>
            <div style="color: #e0e0e0; line-height: 1.8; white-space: pre-wrap;">
{question_without_code}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Mostrar código de ejemplo (priorizar code_example, luego código extraído del texto)
        code_to_show = question_data.get('code_example') or code_in_question
        if code_to_show:
            st.markdown("### 💻 Código:")
            st.code(code_to_show, language=ai_course['language'].lower())
        
        # Mostrar opciones de respuesta
        st.markdown("### Opciones de respuesta:")
        options = question_data.get('options', [])
        selected_option = st.radio(
            "Selecciona tu respuesta:",
            options=options,
            key=f"answer_topic_{section_id}_{current_question_index}",
            label_visibility="collapsed"
        )
    
    # Verificar si ya completó (basado en topic_id, no exercise_id)
    best_attempt = conn.execute("""
        SELECT * FROM ai_exercise_attempts 
        WHERE student_id = ? 
        AND exercise_id IN (SELECT id FROM ai_topic_exercises WHERE topic_id = ?)
        AND is_correct = 1
        ORDER BY score DESC LIMIT 1
    """, (user['username'], section_id)).fetchone()
    
    if best_attempt:
        attempt = dict(best_attempt)
        st.success(f"✅ Ejercicio Completado - Nota: {attempt['score']:.1f}/10")
        
        # Mostrar la explicación si existe
        if question_data.get('explanation'):
            with st.expander("📖 Ver Explicación"):
                st.info(question_data.get('explanation', ''))
        
        st.info("💡 La siguiente sección está desbloqueada")
        
        # Botón para regenerar ejercicio (incluso si ya lo completó)
        if st.button("🔄 Generar Nuevas Preguntas", key=f"regen_completed_ex_{section_id}", help="Genera 15 preguntas nuevas para practicar más"):
            with st.spinner("🤖 Generando nuevas preguntas..."):
                # Eliminar todas las preguntas actuales
                conn.execute("DELETE FROM ai_topic_exercises WHERE topic_id = ?", (section_id,))
                conn.commit()
                st.rerun()
        return
    
    # Si es pregunta de opción múltiple
    # Verificar si ya respondió esta pregunta
    already_answered = False
    session_answers_key = f"answers_topic_{section_id}"
    if session_answers_key in st.session_state:
        for ans in st.session_state[session_answers_key]:
            if ans['question_index'] == current_question_index:
                already_answered = True
                break
    
    # Si ya respondió, mostrar el resultado y botón para siguiente
    if already_answered:
        # Obtener la respuesta guardada
        saved_answer = None
        for ans in st.session_state[session_answers_key]:
            if ans['question_index'] == current_question_index:
                saved_answer = ans
                break
        
        if saved_answer:
            # Mostrar resultado
            if saved_answer['is_correct']:
                st.success(f"✅ ¡Correcto!")
                with st.expander("📖 Explicación"):
                    st.info(question_data.get('explanation', ''))
            else:
                correct_answer = options[saved_answer['correct']]
                st.error(f"❌ Incorrecto")
                st.info(f"💡 La respuesta correcta es: **{correct_answer}**")
                with st.expander("📖 Ver Explicación"):
                    st.info(question_data.get('explanation', ''))
        
        # Verificar si es la última pregunta
        if current_question_index + 1 >= len(questions_list):
            # Calcular puntuación final
            correct_count = sum(1 for ans in st.session_state[session_answers_key] if ans['is_correct'])
            total_questions = len(questions_list)
            score = (correct_count / total_questions) * 10
            percentage = (correct_count / total_questions) * 100
            
            st.markdown("---")
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px;
                border-radius: 15px;
                text-align: center;
                margin: 20px 0;
            ">
                <h2 style="color: white; margin: 0 0 10px 0;">🎯 Resultado Final</h2>
                <h1 style="color: white; margin: 0; font-size: 3em;">{score:.1f}/10</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">
                    {correct_count} de {total_questions} respuestas correctas ({percentage:.0f}%)
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Verificar si ya guardó el intento final
            final_saved_key = f"final_saved_topic_{section_id}"
            if final_saved_key not in st.session_state:
                # Crear o obtener un registro de ejercicio para este tema (para mantener compatibilidad con FOREIGN KEY)
                exercise_record = conn.execute("""
                    SELECT id FROM ai_topic_exercises 
                    WHERE topic_id = ? AND question LIKE '%Evaluación del banco de preguntas%'
                    LIMIT 1
                """, (section_id,)).fetchone()
                
                if not exercise_record:
                    # Crear registro dummy para el banco de preguntas
                    conn.execute("""
                        INSERT INTO ai_topic_exercises 
                        (topic_id, question, exercise_type, points, difficulty_level, topic_area)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        section_id,
                        f"Evaluación del banco de preguntas - {ai_course['language']} - Sección {section_number}",
                        "multiple_choice",
                        100,
                        1,
                        "general"
                    ))
                    conn.commit()
                    exercise_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                else:
                    exercise_id = exercise_record[0]
                
                import json
                feedback = f"Respondiste correctamente {correct_count} de {total_questions} preguntas ({percentage:.0f}%)"
                is_passing = score >= 6
                
                conn.execute("""
                    INSERT INTO ai_exercise_attempts
                    (exercise_id, student_id, submitted_answer, score, max_score, 
                     is_correct, feedback, attempt_number)
                    VALUES (?, ?, ?, ?, ?, ?, ?,
                        (SELECT COALESCE(MAX(attempt_number), 0) + 1 
                         FROM ai_exercise_attempts 
                         WHERE exercise_id = ? AND student_id = ?))
                """, (
                    exercise_id, user['username'], 
                    json.dumps(st.session_state[session_answers_key]),
                    score, 10, 1 if is_passing else 0, feedback,
                    exercise_id, user['username']
                ))
                
                conn.commit()
                st.session_state[final_saved_key] = True
                
                if is_passing:
                    # Marcar sección completada
                    conn.execute("""
                        UPDATE ai_course_topics 
                        SET is_completed = 1, completed_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (section_id,))
                    conn.commit()
                    
                    st.success("🎉 ¡Felicitaciones! Has completado el ejercicio")
                    st.balloons()
                else:
                    st.warning(f"⚠️ Necesitas al menos 6/10 para aprobar. Obtuviste {score:.1f}/10")
            
            # Botón para reiniciar
            if st.button("🔄 Reiniciar Ejercicio", key=f"restart_topic_{section_id}", use_container_width=True):
                if session_answers_key in st.session_state:
                    del st.session_state[session_answers_key]
                if final_saved_key in st.session_state:
                    del st.session_state[final_saved_key]
                st.session_state[session_key] = 0
                st.rerun()
        else:
            # Botón para siguiente pregunta
            if st.button("➡️ Siguiente Pregunta", key=f"next_topic_{section_id}_{current_question_index}", type="primary", use_container_width=True):
                st.session_state[session_key] += 1
                st.rerun()
    
    else:
        # No ha respondido aún, mostrar botón de verificar
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✅ Verificar Respuesta", key=f"eval_topic_{section_id}_{current_question_index}", type="primary", use_container_width=True):
                if selected_option:
                    # Verificar si la respuesta es correcta
                    correct_index = question_data.get('correct_index', 0)
                    selected_index = options.index(selected_option)
                    is_correct = selected_index == correct_index
                    
                    # Guardar respuesta en session_state
                    if session_answers_key not in st.session_state:
                        st.session_state[session_answers_key] = []
                    
                    st.session_state[session_answers_key].append({
                        'question_index': current_question_index,
                        'selected': selected_index,
                        'correct': correct_index,
                        'is_correct': is_correct
                    })
                    
                    st.rerun()
                else:
                    st.warning("⚠️ Por favor selecciona una opción")
        
        with col2:
            # Botón de pista específica para la pregunta
            if st.button("💡 Ver Pista", key=f"hint_topic_{section_id}_{current_question_index}", use_container_width=True):
                # Generar pista específica basada en la pregunta
                question_text = question_data.get('question', '').lower()
                topic = section.get('title', 'este tema')
                
                if 'imprime' in question_text or 'print' in question_text or 'console.log' in question_text:
                    hint = f"💡 Ejecuta el código mentalmente línea por línea. ¿Qué valores se imprimen? Recuerda los conceptos de {topic}."
                elif 'resultado' in question_text or 'retorna' in question_text or 'devuelve' in question_text:
                    hint = f"💡 Analiza qué valor devuelve la función. Sigue el flujo del código paso a paso considerando {topic}."
                elif 'error' in question_text:
                    hint = f"💡 Revisa la sintaxis y lógica del código. ¿Hay algún error relacionado con {topic}?"
                elif 'tipo' in question_text or 'type' in question_text:
                    hint = f"💡 Piensa en los tipos de datos involucrados. ¿Qué tipo resulta de esta operación según {topic}?"
                else:
                    hint = f"💡 Analiza el código cuidadosamente. Ejecuta mentalmente cada línea considerando los conceptos de {topic}."
                
                st.info(hint)



def render_section_chat(conn, user, model, section, ai_course):
    """Renderiza chat IA con preguntas sugeridas"""
    
    section_id = section['id']
    
    st.markdown("""
    <div style="text-align: center; margin: 20px 0;">
        <h3 style="
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2em;
            font-weight: bold;
        ">💬 Chat IA - Pregunta sobre este tema</h3>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #1a2332 0%, #0f1923 100%);
        padding: 15px;
        border-radius: 15px;
        text-align: center;
        border-left: 5px solid #4da6ff;
        margin-bottom: 20px;
    ">
        <p style="color: #b3d9ff; margin: 0;">
            💡 Haz preguntas específicas sobre: <strong style="color: #4da6ff;">{fix_language_in_text(section['title'], ai_course['language'])}</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # PREGUNTAS SUGERIDAS
    st.markdown("#### 🤔 Preguntas Sugeridas")
    st.markdown("*Haz clic en una pregunta para usarla:*")
    
    # Generar preguntas
    if f'suggested_questions_{section_id}' not in st.session_state:
        from utils_ai import generate_suggested_questions
        questions = generate_suggested_questions(
            model,
            ai_course['language'],
            section['title'],
            ai_course['level']
        )
        st.session_state[f'suggested_questions_{section_id}'] = questions
    
    suggested_questions = st.session_state.get(f'suggested_questions_{section_id}', [])
    
    # Historial de chat
    chat_key = f"chat_history_{section_id}"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []
    
    # Procesar pregunta sugerida si fue clickeada
    if f'process_suggested_{section_id}' in st.session_state:
        suggested_q = st.session_state[f'process_suggested_{section_id}']
        del st.session_state[f'process_suggested_{section_id}']
        
        with st.spinner("🤖 La IA está pensando..."):
            st.session_state[chat_key].append({
                'role': 'user',
                'content': suggested_q
            })
            
            prompt = f"""
            Eres un tutor experto en {ai_course['language']} nivel {ai_course['level']}.
            
            TEMA: {section['title']}
            DESCRIPCIÓN: {section.get('description', '')}
            
            PREGUNTA: {suggested_q}
            
            Responde de manera clara y educativa.
            Usa ejemplos de código cuando sea apropiado.
            Adapta tu respuesta al nivel {ai_course['level']}.
            """
            
            try:
                response = model.generate_content(prompt)
                answer = response.text
                
                st.session_state[chat_key].append({
                    'role': 'assistant',
                    'content': answer
                })
                
                st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")
    
    # Mostrar botones de preguntas sugeridas en 2 columnas
    if suggested_questions:
        cols = st.columns(2)
        for idx, question in enumerate(suggested_questions):
            with cols[idx % 2]:
                if st.button(f"💡 {question}", key=f"suggest_{section_id}_{idx}", use_container_width=True):
                    st.session_state[f'process_suggested_{section_id}'] = question
                    st.rerun()
    
    st.markdown("---")
    
    # Mostrar historial
    for msg in st.session_state[chat_key]:
        if msg['role'] == 'user':
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 15px 20px;
                border-radius: 15px 15px 5px 15px;
                margin: 10px 0 10px 50px;
            ">
                <p style="color: white; margin: 0;"><strong>👤 Tú:</strong></p>
                <p style="color: rgba(255, 255, 255, 0.95); margin: 5px 0 0 0;">{msg['content']}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #2d2d2d 0%, #1a1a1a 100%);
                padding: 15px 20px;
                border-radius: 15px 15px 15px 5px;
                margin: 10px 50px 10px 0;
                border-left: 5px solid #667eea;
            ">
                <p style="color: #e0e0e0; margin: 0;"><strong>🤖 IA:</strong></p>
                <p style="color: #d0d0d0; margin: 5px 0 0 0;">{msg['content']}</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Input de pregunta
    question = st.text_area(
        "Tu pregunta:",
        key=f"question_{section_id}",
        placeholder=f"Pregunta algo sobre {fix_language_in_text(section['title'], ai_course['language'])}...",
        height=100
    )
    
    if st.button("📤 Enviar Pregunta", key=f"send_{section_id}", type="primary"):
        if question.strip():
            with st.spinner("🤖 La IA está pensando..."):
                st.session_state[chat_key].append({
                    'role': 'user',
                    'content': question
                })
                
                prompt = f"""
                Eres un tutor experto en {ai_course['language']} nivel {ai_course['level']}.
                
                TEMA: {section['title']}
                DESCRIPCIÓN: {section.get('description', '')}
                
                PREGUNTA: {question}
                
                Responde de manera clara y educativa.
                Usa ejemplos de código cuando sea apropiado.
                Adapta tu respuesta al nivel {ai_course['level']}.
                """
                
                try:
                    response = model.generate_content(prompt)
                    answer = response.text
                    
                    st.session_state[chat_key].append({
                        'role': 'assistant',
                        'content': answer
                    })
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        else:
            st.warning("⚠️ Escribe una pregunta primero")



def render_course_progress(conn, user, ai_course, sections_rows):
    """Renderiza el progreso del curso - OPTIMIZADO"""
    
    st.markdown("## 📊 Tu Progreso en el Curso")
    
    # Info sobre rendimiento
    st.info("💡 **Tip:** Esta vista está optimizada para carga rápida. Si experimentas lentitud, intenta cerrar otras pestañas del navegador.")
    
    # Convertir a dict una sola vez para evitar conversiones repetidas
    sections = [dict(s) if not isinstance(s, dict) else s for s in sections_rows]
    
    total_sections = len(sections)
    completed_sections = sum(1 for s in sections if s.get('is_completed', 0))
    progress_pct = ai_course.get('progress_percentage', 0)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📈 Progreso Total", f"{progress_pct:.1f}%")
    
    with col2:
        st.metric("✅ Secciones", f"{completed_sections}/{total_sections}")
    
    with col3:
        st.metric("🎯 Nivel", ai_course['level'].title())
    
    # Barra de progreso personalizada con gradiente azul a rojo
    st.markdown(f"""
    <div style="margin: 20px 0;">
        <div style="
            width: 100%;
            height: 30px;
            background: linear-gradient(90deg, #1a1a2e 0%, #16213e 100%);
            border-radius: 15px;
            overflow: hidden;
            border: 2px solid #667eea;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
        ">
            <div style="
                width: {progress_pct}%;
                height: 100%;
                background: linear-gradient(90deg, 
                    #667eea 0%,
                    #764ba2 25%,
                    #f093fb 50%,
                    #f5576c 75%,
                    #ff0844 100%
                );
                border-radius: 13px;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: width 0.5s ease-in-out;
                box-shadow: 0 0 20px rgba(102, 126, 234, 0.5);
            ">
                <span style="
                    color: white;
                    font-weight: bold;
                    font-size: 14px;
                    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.5);
                ">
                    {progress_pct:.1f}%
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 📋 Estado de las Secciones")
    
    # Renderizar todas las secciones de una vez (más eficiente)
    progress_html = []
    for section in sections:
        is_completed = section.get('is_completed', 0)
        is_unlocked = section.get('is_unlocked', 0)
        
        if is_completed:
            icon, status, color = "✅", "Completada", "#28a745"
        elif is_unlocked:
            icon, status, color = "📖", "En Progreso", "#ffc107"
        else:
            icon, status, color = "🔒", "Bloqueada", "#6c757d"
        
        progress_html.append(f"""
        <div style="
            background: linear-gradient(135deg, #2d2d2d 0%, #1a1a1a 100%);
            padding: 15px 20px;
            border-radius: 10px;
            margin-bottom: 10px;
            border-left: 5px solid {color};
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
        ">
            <p style="color: white; margin: 0; font-size: 1.1em;">
                {icon} <strong>Sección {section['topic_number']}: {fix_language_in_text(section['title'], ai_course['language'])}</strong>
            </p>
            <p style="color: {color}; margin: 5px 0 0 0; font-size: 0.95em;">
                {status}
            </p>
        </div>
        """)
    
    # Renderizar todo de una vez
    st.markdown(''.join(progress_html), unsafe_allow_html=True)


def render_final_exam(conn, user, model, ai_course, sections_rows):
    """Renderiza el examen final - Siempre disponible"""

    st.markdown("## 🎓 Examen Final del Curso")

    # Verificar si ya aprobó (solo mostrar mensaje, no bloquear)
    final_attempt = conn.execute("""
        SELECT * FROM ai_course_final_exams
        WHERE student_id = ? AND ai_course_id = ? AND passed = 1
        ORDER BY completed_at DESC LIMIT 1
    """, (user['username'], ai_course['id'])).fetchone()

    if final_attempt:
        attempt = dict(final_attempt)
        st.success(f"🎉 ¡Felicidades! Aprobaste con {attempt['score']:.1f}/10")

    st.info("💡 El examen final está disponible en cualquier momento. Necesitas nota ≥6/10 (60%) para aprobar")

    # Botón para limpiar examen corrupto si existe
    if st.session_state.get('final_exam_started'):
        if st.button("🔄 Reiniciar Examen", type="secondary", use_container_width=True):
            # Limpiar todo el estado del examen
            for key in ['final_exam', 'final_exam_started', 'exam_responses', 'exam_page']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    else:
        # Solo mostrar el botón de tomar examen si NO hay uno iniciado
        if st.button("🎓 Tomar Examen Final", type="primary", use_container_width=True):
            # Verificar que el modelo esté disponible
            if not model:
                st.error("❌ El modelo de IA no está disponible. Por favor, contacta al administrador.")
                return
            
            with st.spinner("🤖 Generando examen... Esto puede tomar unos segundos"):
                from utils_ai import generate_creative_final_exam

                try:
                    # Generar examen con IA - 20 preguntas aleatorias
                    exam_data = generate_creative_final_exam(
                        model=model,
                        language=ai_course['language'],
                        level=ai_course['level'],
                        num_questions=20
                    )

                    if not exam_data or not exam_data.get('questions'):
                        st.error(f"❌ Error generando examen para {ai_course['language']} - {ai_course['level']}")
                        metadata = exam_data.get('metadata', {}) if exam_data else {}
                        if 'error' in metadata:
                            st.error(f"Detalles: {metadata['error']}")
                        st.info("💡 Intenta nuevamente en unos momentos")
                        return

                    # Validar que tenemos suficientes preguntas
                    metadata = exam_data.get('metadata', {})
                    total_questions = metadata.get('total_questions', 0)

                    if total_questions < 10:
                        st.error("❌ No se generaron suficientes preguntas. Intenta nuevamente.")
                        return

                    # Guardar examen en session_state
                    st.session_state['final_exam'] = exam_data
                    st.session_state['final_exam_started'] = True
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error generando examen: {str(e)}")
                    st.info("💡 Intenta nuevamente en unos momentos")
                    import traceback
                    st.code(traceback.format_exc())
                    return

    # Si el examen ya comenzó, mostrarlo
    if st.session_state.get('final_exam_started'):
        exam_data = st.session_state.get('final_exam')
        if not exam_data or not exam_data.get('questions'):
            st.error("Error: No se encontró el examen")
            for key in ['final_exam_started', 'final_exam']:
                if key in st.session_state:
                    del st.session_state[key]
            return

        questions = exam_data['questions']
        
        # Inicializar estado
        if 'exam_responses' not in st.session_state:
            st.session_state['exam_responses'] = {}
        if 'exam_page' not in st.session_state:
            st.session_state['exam_page'] = 0

        current_page = st.session_state['exam_page']
        total_pages = len(questions)
        
        # Validar página
        if current_page >= total_pages:
            current_page = 0
            st.session_state['exam_page'] = 0

        q = questions[current_page]
        q_num = current_page + 1

        # Header con diseño mejorado
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; margin-bottom: 20px; text-align: center;">
            <h3 style="color: white; margin: 0;">Pregunta {q_num} de {total_pages}</h3>
        </div>
        """, unsafe_allow_html=True)
        
        st.progress(q_num / total_pages)

        # Mostrar pregunta - Separar texto de código para mejor claridad
        question_text = q['question']
        
        # Extraer código si está en la pregunta
        import re
        code_match = re.search(r'```python\n(.*?)\n```', question_text, re.DOTALL)
        
        if code_match:
            # Separar pregunta y código
            code_block = code_match.group(1)
            question_without_code = question_text[:code_match.start()].strip()
            
            # Mostrar pregunta sin código
            st.markdown(f"### {question_without_code}")
            
            # Mostrar código en un bloque separado con título
            st.markdown("**Código a analizar:**")
            st.code(code_block, language=ai_course['language'].lower())
        else:
            # Si no hay código en la pregunta, mostrar normal
            st.markdown(f"### {question_text}")

        # Respuesta - Guardar con doble mecanismo para mayor confiabilidad
        default = 0
        if q_num in st.session_state['exam_responses']:
            default = st.session_state['exam_responses'][q_num].get('selected_index', 0)

        # CRÍTICO: Guardar el índice correcto de ESTA pregunta específica
        current_question_correct_index = q['correct_answer']
        current_question_options = q['options'].copy()  # Copia para evitar modificaciones

        # Renderizar radio button SIN callback (Streamlit callbacks son problemáticos)
        selected = st.radio(
            "Selecciona tu respuesta:", 
            q['options'], 
            index=default, 
            key=f"q{q_num}_radio"
        )
        
        # INMEDIATAMENTE después del radio, guardar la respuesta
        # Esto se ejecuta en cada render, capturando el valor actual
        try:
            selected_index = current_question_options.index(selected)
            
            # Guardar con el índice correcto de ESTA pregunta
            st.session_state['exam_responses'][q_num] = {
                'selected_index': selected_index,
                'correct_index': current_question_correct_index
            }
            
            # Logging detallado
            print(f"✅ Guardada respuesta pregunta {q_num}:")
            print(f"   Seleccionada: índice {selected_index} = '{selected[:40]}...'")
            print(f"   Correcta: índice {current_question_correct_index} = '{current_question_options[current_question_correct_index][:40]}...'")
            print(f"   ¿Es correcta?: {selected_index == current_question_correct_index}")
        except (ValueError, KeyError) as e:
            print(f"❌ Error guardando respuesta pregunta {q_num}: {e}")
            print(f"   Texto seleccionado: '{selected}'")
            print(f"   Opciones disponibles: {current_question_options}")

        st.markdown("---")

        # Navegación
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col1:
            if current_page > 0:
                if st.button("⬅️ Anterior", use_container_width=True, key="btn_prev"):
                    st.session_state['exam_page'] -= 1
                    st.rerun()
        
        with col2:
            answered = len(st.session_state['exam_responses'])
            st.info(f"📊 Respondidas: {answered}/{total_pages}")
        
        with col3:
            if current_page < total_pages - 1:
                if st.button("Siguiente ➡️", use_container_width=True, key="btn_next"):
                    st.session_state['exam_page'] += 1
                    st.rerun()

        # Enviar
        if current_page == total_pages - 1:
            st.markdown("---")
            
            answered = len(st.session_state['exam_responses'])
            if answered < total_pages:
                st.warning(f"⚠️ Faltan {total_pages - answered} preguntas por responder")
            
            if st.button("📝 Enviar Examen Final", type="primary", use_container_width=True):
                # Verificar que todas las preguntas estén respondidas
                if len(st.session_state['exam_responses']) < total_pages:
                    missing = total_pages - len(st.session_state['exam_responses'])
                    st.error(f"❌ Faltan {missing} preguntas por responder. Por favor, revisa todas las preguntas.")
                    
                    # Mostrar qué preguntas faltan
                    missing_questions = []
                    for i in range(1, total_pages + 1):
                        if i not in st.session_state['exam_responses']:
                            missing_questions.append(i)
                    
                    if missing_questions:
                        st.warning(f"Preguntas sin responder: {', '.join(map(str, missing_questions))}")
                    return

                responses = st.session_state['exam_responses']
                
                # LOGGING DETALLADO PARA DEBUGGING
                print("\n" + "="*80)
                print("🔍 DEBUG: EVALUACIÓN DEL EXAMEN")
                print("="*80)
                print(f"Total de preguntas: {total_pages}")
                print(f"Respuestas guardadas: {len(responses)}")
                print("\nDETALLE POR PREGUNTA:")
                
                correct_count = 0
                for q_idx in range(1, total_pages + 1):
                    if q_idx in responses:
                        resp = responses[q_idx]
                        is_correct = resp['selected_index'] == resp['correct_index']
                        if is_correct:
                            correct_count += 1
                        
                        # Obtener la pregunta para mostrar más info
                        question_obj = questions[q_idx - 1]
                        selected_option = question_obj['options'][resp['selected_index']] if resp['selected_index'] < len(question_obj['options']) else "ÍNDICE INVÁLIDO"
                        correct_option = question_obj['options'][resp['correct_index']] if resp['correct_index'] < len(question_obj['options']) else "ÍNDICE INVÁLIDO"
                        
                        status = "✅ CORRECTA" if is_correct else "❌ INCORRECTA"
                        print(f"\nPregunta {q_idx}: {status}")
                        print(f"  Pregunta: {question_obj['question'][:60]}...")
                        print(f"  Seleccionada (índice {resp['selected_index']}): {selected_option[:50]}...")
                        print(f"  Correcta (índice {resp['correct_index']}): {correct_option[:50]}...")
                    else:
                        print(f"\nPregunta {q_idx}: ⚠️ SIN RESPUESTA")
                
                print(f"\n{'='*80}")
                print(f"RESULTADO: {correct_count}/{total_pages} correctas")
                print(f"{'='*80}\n")
                
                correct = correct_count
                score = (correct / total_pages) * 10
                passed = correct >= (total_pages * 0.6)
                
                # Debug: mostrar cálculo
                print(f"DEBUG EXAM: correct={correct}, total={total_pages}, score={score}, passed={passed}")
                print(f"DEBUG EXAM: responses={responses}")

                import json
                attempt_count = conn.execute("""
                    SELECT COUNT(*) as count FROM ai_course_final_exams
                    WHERE student_id = ? AND ai_course_id = ?
                """, (user['username'], ai_course['id'])).fetchone()['count']
                
                conn.execute("""
                    INSERT INTO ai_course_final_exams
                    (ai_course_id, student_id, questions_data, responses_data, 
                     score, max_score, percentage, passed, attempt_number, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    ai_course['id'], user['username'],
                    json.dumps(questions), json.dumps(responses),
                    score, 10, (correct / total_pages) * 100,
                    1 if passed else 0, attempt_count + 1
                ))
                conn.commit()

                if passed:
                    conn.execute("""
                        UPDATE ai_courses 
                        SET status = 'completed', display_status = 'completed', completed_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND student_id = ?
                    """, (ai_course['id'], user['username']))
                    conn.commit()

                for key in ['final_exam', 'final_exam_started', 'exam_responses', 'exam_page']:
                    if key in st.session_state:
                        del st.session_state[key]

                # Mostrar resultados detallados
                st.markdown("---")
                st.markdown("### 📊 Resultados del Examen")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Correctas", f"{correct}/{total_pages}")
                with col2:
                    st.metric("Puntuación", f"{score:.1f}/10")
                with col3:
                    st.metric("Porcentaje", f"{(correct/total_pages)*100:.0f}%")
                
                st.markdown("---")

                if passed:
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px; border-radius: 15px; text-align: center; margin: 20px 0;">
                        <h1 style="color: white; margin: 0 0 15px 0;">🎉 ¡FELICITACIONES! 🎉</h1>
                        <h2 style="color: white; margin: 0;">Aprobaste con {correct}/{total_pages} ({score:.1f}/10)</h2>
                    </div>
                    """, unsafe_allow_html=True)
                    st.balloons()
                    st.success("✅ El curso ha sido marcado como completado")
                    st.info("📚 Puedes encontrar este curso en 'Mis Cursos' → Cursos Terminados")
                else:
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 30px; border-radius: 15px; text-align: center; margin: 20px 0;">
                        <h1 style="color: white; margin: 0 0 15px 0;">😔 No Aprobaste</h1>
                        <h2 style="color: white; margin: 0;">Puntuación: {correct}/{total_pages} ({score:.1f}/10)</h2>
                    </div>
                    """, unsafe_allow_html=True)
                    st.info(f"💡 Necesitas al menos {int(total_pages * 0.6)}/{total_pages} para aprobar. Puedes volver a intentarlo.")
                    # Botón para volver al curso
                    if st.button("📚 Volver al Curso", type="primary", use_container_width=True):
                        st.rerun()
                
                # No hacer rerun aquí, dejar que Streamlit maneje el estado





def render_course_settings(conn, user, model, ai_course, ai_course_id):
    """Renderiza configuración del curso"""
    
    st.markdown("### ⚙️ Configuración del Curso")
    
    st.markdown("#### 📋 Información")
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(f"**Lenguaje:** {ai_course['language']}")
        st.info(f"**Nivel:** {ai_course['level'].title()}")
    
    with col2:
        st.info(f"**Creado:** {ai_course['created_at'][:10]}")
        st.info(f"**Estado:** {ai_course.get('status', 'active').title()}")
    
    st.markdown("---")
    
    # Botón para limpiar caché y regenerar
    st.markdown("#### 🔄 Regenerar Contenido")
    st.info("Si el contenido muestra el lenguaje incorrecto, usa este botón para regenerar todo desde cero.")
    
    # Usar session_state para controlar el flujo de confirmación
    if 'confirm_regenerate' not in st.session_state:
        st.session_state.confirm_regenerate = False
    
    if not st.session_state.confirm_regenerate:
        if st.button("🗑️ Limpiar Caché y Regenerar Todo", type="secondary", use_container_width=True, key="btn_regenerate_1"):
            st.session_state.confirm_regenerate = True
            st.rerun()
    else:
        st.warning("⚠️ ¿Estás seguro? Esta acción eliminará todo el contenido actual y lo regenerará desde cero.")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✅ Sí, Regenerar", type="primary", use_container_width=True, key="btn_confirm_regenerate"):
                st.session_state.confirm_regenerate = False
                
                with st.spinner("🤖 Limpiando y regenerando curso completo..."):
                    # Eliminar TODO el contenido
                    conn.execute("DELETE FROM ai_course_materials WHERE ai_course_id = ?", (ai_course_id,))
                    conn.execute("DELETE FROM ai_topic_exercises WHERE ai_course_id = ?", (ai_course_id,))
                    conn.execute("DELETE FROM ai_course_topics WHERE ai_course_id = ?", (ai_course_id,))
                    conn.execute("UPDATE ai_courses SET progress_percentage = 0 WHERE id = ?", (ai_course_id,))
                    conn.commit()
                    
                    st.success("✅ Caché limpiado. Regenerando contenido...")
                    
                    # Regenerar estructura
                    from utils_ai import generate_course_topics_structure, generate_topic_materials_spanish, generate_lesson_content
                    
                    topics_structure = generate_course_topics_structure(
                        model, 
                        ai_course['language'], 
                        ai_course['level'],
                        8
                    )
                    
                    if topics_structure:
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        total_sections = len(topics_structure)
                        
                        for idx, topic_data in enumerate(topics_structure, 1):
                            progress = idx / total_sections
                            progress_bar.progress(progress)
                            status_text.info(f"📝 Generando sección {idx}/{total_sections}: {topic_data['title']}")
                            
                            # Insertar sección
                            # Asegurar que objectives sea un string
                            objectives = topic_data.get('objectives', '')
                            if isinstance(objectives, list):
                                objectives = '. '.join(objectives)
                            elif not isinstance(objectives, str):
                                objectives = str(objectives)
                            
                            topic_cursor = conn.execute("""
                                INSERT INTO ai_course_topics 
                                (ai_course_id, topic_number, title, description, objectives, 
                                 estimated_hours, order_index, is_unlocked, is_completed)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                ai_course_id,
                                topic_data['topic_number'],
                                topic_data['title'],
                                topic_data.get('description', ''),
                                objectives,
                                topic_data.get('estimated_hours', 3),
                                topic_data.get('order_index', idx - 1),
                                1,  # Todas las secciones desbloqueadas desde el inicio
                                0
                            ))
                            
                            section_id = topic_cursor.lastrowid
                            
                            # Generar contenido de la lección
                            lesson_content = generate_lesson_content(
                                model,
                                ai_course['language'],
                                topic_data['title'],
                                topic_data.get('description', ''),
                                ai_course['level']
                            )
                            
                            # Guardar contenido
                            conn.execute("""
                                INSERT INTO ai_course_materials 
                                (ai_course_id, topic_id, type, title, description, url, 
                                 order_index, estimated_minutes, difficulty_level, language_content)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                ai_course_id, section_id, 'tutorial',
                                f"Lección: {topic_data['title']}", lesson_content,
                                '#', 0, 30, 1, 'es'
                            ))
                            
                            # GENERAR 15 PREGUNTAS CON CÓDIGO AUTOMÁTICAMENTE
                            from utils_ai import generate_topic_evaluation
                            
                            evaluation_questions = generate_topic_evaluation(
                                model,
                                ai_course['language'],
                                topic_data['title'],
                                ai_course['level'],
                                difficulty_setting='normal'
                            )
                            
                            # Guardar preguntas en la base de datos
                            if evaluation_questions and isinstance(evaluation_questions, list):
                                import json
                                
                                # Mapeo de dificultad numérica a texto
                                difficulty_map = {1: 'easy', 2: 'medium', 3: 'hard', 4: 'hard', 5: 'hard'}
                                
                                for question in evaluation_questions:
                                    difficulty_num = question.get('difficulty', 1)
                                    difficulty_text = difficulty_map.get(difficulty_num, 'medium')
                                    
                                    conn.execute("""
                                        INSERT INTO ai_topic_exercises 
                                        (topic_id, title, description, question, options, correct_index, explanation, 
                                         points, difficulty, difficulty_level, topic_area, code_example)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, (
                                        section_id,
                                        f"Pregunta sobre {topic_data['title']}",
                                        f"Evaluación de {topic_data['title']}",
                                        question.get('question', ''),
                                        json.dumps(question.get('options', []), ensure_ascii=False),
                                        question.get('correct_index', 0),
                                        question.get('explanation', ''),
                                        question.get('points', 20),
                                        difficulty_text,
                                        difficulty_num,
                                        question.get('topic_area', 'general'),
                                        question.get('code_example', '')
                                    ))
                            
                            # Generar materiales
                            topic_materials = generate_topic_materials_spanish(
                                model, 
                                ai_course['language'], 
                                topic_data['title'],
                                topic_data.get('description', ''),
                                ai_course['level']
                            )
                            
                            if topic_materials:
                                for mat_idx, material in enumerate(topic_materials):
                                    conn.execute("""
                                        INSERT INTO ai_course_materials 
                                        (ai_course_id, topic_id, type, title, description, url, 
                                         order_index, estimated_minutes, difficulty_level, language_content)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, (
                                        ai_course_id, section_id,
                                        material.get('type', 'video'),
                                        material.get('title', ''),
                                        material.get('description', ''),
                                        material.get('url', '#'),
                                        material.get('order_index', mat_idx),
                                        material.get('estimated_minutes', 30),
                                        material.get('difficulty_level', 1),
                                        material.get('language_content', 'es')
                                    ))
                        
                        conn.commit()
                        progress_bar.progress(1.0)
                        status_text.success("✅ ¡Curso regenerado completamente!")
                        st.balloons()
                        
                        import time
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("❌ Error al generar estructura")
        
        with col2:
            if st.button("❌ Cancelar", use_container_width=True, key="btn_cancel_regenerate"):
                st.session_state.confirm_regenerate = False
                st.rerun()
    
    st.markdown("---")
    
    # ELIMINAR CURSO COMPLETAMENTE
    st.markdown("#### 🗑️ Eliminar Curso")
    st.error("⚠️ PELIGRO: Esta acción eliminará el curso PERMANENTEMENTE")
    
    # Usar session_state para controlar el flujo de confirmación de eliminación
    if 'confirm_delete' not in st.session_state:
        st.session_state.confirm_delete = False
    
    if not st.session_state.confirm_delete:
        if st.button("🗑️ Eliminar Este Curso Completamente", type="secondary", use_container_width=True, key="btn_delete_1"):
            st.session_state.confirm_delete = True
            st.rerun()
    else:
        st.warning("⚠️ ¿Estás COMPLETAMENTE seguro? Esta acción NO se puede deshacer.")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✅ Sí, Eliminar Permanentemente", type="primary", use_container_width=True, key="btn_confirm_delete"):
                st.session_state.confirm_delete = False
                
                # Eliminar TODO relacionado con el curso
                conn.execute("DELETE FROM ai_course_materials WHERE ai_course_id = ?", (ai_course_id,))
                conn.execute("DELETE FROM ai_topic_exercises WHERE ai_course_id = ?", (ai_course_id,))
                conn.execute("DELETE FROM ai_exercise_attempts WHERE exercise_id IN (SELECT id FROM ai_topic_exercises WHERE ai_course_id = ?)", (ai_course_id,))
                conn.execute("DELETE FROM ai_course_topics WHERE ai_course_id = ?", (ai_course_id,))
                conn.execute("DELETE FROM ai_courses WHERE id = ?", (ai_course_id,))
                conn.commit()
                
                st.success("✅ Curso eliminado completamente")
                st.info("💡 Puedes crear un nuevo curso cuando quieras")
                
                import time
                time.sleep(2)
                st.rerun()
        
        with col2:
            if st.button("❌ Cancelar", use_container_width=True, key="btn_cancel_delete"):
                st.session_state.confirm_delete = False
                st.rerun()
    
    st.markdown("---")
    
    # Cambiar dificultad
    st.markdown("#### 🎚️ Cambiar Dificultad")
    st.warning("⚠️ Al cambiar la dificultad, se regenerará TODO el contenido automáticamente")
    
    new_level = st.selectbox(
        "Nueva dificultad:",
        ["principiante", "intermedio", "avanzado"],
        index=["principiante", "intermedio", "avanzado"].index(ai_course['level'])
    )
    
    if new_level != ai_course['level']:
        if st.button("🔄 Cambiar y Regenerar Ahora", type="primary", use_container_width=True):
            with st.spinner("🤖 Cambiando dificultad y regenerando curso completo..."):
                # 1. Eliminar contenido antiguo
                conn.execute("DELETE FROM ai_course_materials WHERE ai_course_id = ?", (ai_course_id,))
                conn.execute("DELETE FROM ai_topic_exercises WHERE ai_course_id = ?", (ai_course_id,))
                conn.execute("DELETE FROM ai_course_topics WHERE ai_course_id = ?", (ai_course_id,))
                
                # 2. Actualizar dificultad
                conn.execute("""
                    UPDATE ai_courses 
                    SET level = ?, progress_percentage = 0
                    WHERE id = ?
                """, (new_level, ai_course_id))
                
                conn.commit()
                
                st.success(f"✅ Dificultad cambiada a: {new_level}")
                
                # 3. Regenerar contenido automáticamente
                try:
                    from utils_ai import generate_course_topics_structure, generate_topic_materials_spanish, generate_lesson_content
                    
                    st.info("📚 Generando nueva estructura del curso...")
                    topics_structure = generate_course_topics_structure(
                        model, 
                        ai_course['language'], 
                        new_level,  # Usar la nueva dificultad
                        8
                    )
                    
                    if not topics_structure:
                        st.error("❌ Error al generar estructura")
                        return
                    
                    # Barra de progreso
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    total_sections = len(topics_structure)
                    
                    # Crear cada sección con su contenido
                    for idx, topic_data in enumerate(topics_structure, 1):
                        progress = idx / total_sections
                        progress_bar.progress(progress)
                        status_text.info(f"📝 Generando sección {idx}/{total_sections}: {topic_data['title']}")
                        
                        # Insertar sección
                        # Asegurar que objectives sea un string
                        objectives = topic_data.get('objectives', '')
                        if isinstance(objectives, list):
                            objectives = '. '.join(objectives)
                        elif not isinstance(objectives, str):
                            objectives = str(objectives)
                        
                        topic_cursor = conn.execute("""
                            INSERT INTO ai_course_topics 
                            (ai_course_id, topic_number, title, description, objectives, 
                             estimated_hours, order_index, is_unlocked, is_completed)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            ai_course_id,
                            topic_data['topic_number'],
                            topic_data['title'],
                            topic_data['description'],
                            objectives,
                            topic_data.get('estimated_hours', 3),
                            topic_data.get('order_index', 0),
                            1,  # Todas las secciones desbloqueadas desde el inicio
                            0
                        ))
                        
                        topic_id = topic_cursor.lastrowid
                        
                        # Generar contenido de la lección
                        lesson_content = generate_lesson_content(
                            model,
                            ai_course['language'],
                            topic_data['title'],
                            topic_data.get('description', ''),
                            new_level  # Usar la nueva dificultad
                        )
                        
                        if lesson_content:
                            conn.execute("""
                                INSERT INTO ai_course_materials 
                                (ai_course_id, topic_id, type, title, description, url, 
                                 order_index, estimated_minutes, difficulty_level, language_content)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                ai_course_id, topic_id, 'tutorial',
                                f"Lección: {topic_data['title']}", lesson_content, 
                                '#', 0, 30, 1, 'es'
                            ))
                            
                            # Las preguntas ahora se cargan del banco pre-generado
                            # No es necesario generar preguntas aquí
                        
                        # Generar materiales adicionales
                        topic_materials = generate_topic_materials_spanish(
                            model, 
                            ai_course['language'], 
                            topic_data['title'], 
                            topic_data['description'], 
                            new_level  # Usar la nueva dificultad
                        )
                        
                        if topic_materials:
                            for material in topic_materials:
                                # Validar que el tipo sea uno de los permitidos
                                valid_types = ['video', 'website', 'tutorial', 'documentation', 'exercise']
                                material_type = material.get('type', 'website')
                                if material_type not in valid_types:
                                    material_type = 'website'  # Fallback a website si el tipo no es válido
                                
                                conn.execute("""
                                    INSERT INTO ai_course_materials 
                                    (ai_course_id, topic_id, type, title, description, url, 
                                     order_index, estimated_minutes, difficulty_level, language_content)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    ai_course_id, topic_id, material_type, 
                                    material.get('title', ''), material.get('description', ''), 
                                    material.get('url', '#'), material.get('order_index', 1), 
                                    material.get('estimated_minutes', 30),
                                    material.get('difficulty_level', 1), 
                                    material.get('language_content', 'es')
                                ))
                    
                    conn.commit()
                    progress_bar.progress(1.0)
                    status_text.success("✅ ¡Curso regenerado completamente!")
                    
                    st.balloons()
                    st.success(f"🎉 Curso regenerado con dificultad: {new_level.upper()}")
                    
                    import time
                    time.sleep(2)
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error al regenerar: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
    
    st.markdown("---")
    
    # Pausar/Reanudar
    st.markdown("#### ⏸️ Pausar Curso")
    
    if ai_course.get('status') == 'active':
        if st.button("⏸️ Pausar", use_container_width=True):
            conn.execute("UPDATE ai_courses SET status = 'paused' WHERE id = ?", (ai_course_id,))
            conn.commit()
            st.success("⏸️ Curso pausado")
            st.rerun()
    else:
        if st.button("▶️ Reanudar", use_container_width=True):
            conn.execute("UPDATE ai_courses SET status = 'active' WHERE id = ?", (ai_course_id,))
            conn.commit()
            st.success("▶️ Curso reanudado")
            st.rerun()
    
    st.markdown("---")
    
    # Eliminar
    st.markdown("#### 🗑️ Eliminar Curso")
    st.error("⚠️ Esta acción no se puede deshacer")
    
    if st.checkbox("Confirmar eliminación"):
        if st.button("🗑️ Eliminar Permanentemente", type="secondary"):
            conn.execute("DELETE FROM ai_course_materials WHERE ai_course_id = ?", (ai_course_id,))
            conn.execute("DELETE FROM ai_topic_exercises WHERE ai_course_id = ?", (ai_course_id,))
            conn.execute("DELETE FROM ai_course_topics WHERE ai_course_id = ?", (ai_course_id,))
            conn.execute("DELETE FROM ai_courses WHERE id = ?", (ai_course_id,))
            conn.commit()
            
            st.success("✅ Curso eliminado")
            st.session_state.view_mode = 'dashboard'
            st.rerun()
