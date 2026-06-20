package com.hermes.gui.util

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import com.hermes.gui.ui.theme.CodeBlockBg
import com.hermes.gui.ui.theme.CodeBlockText

/**
 * Simple markdown renderer for chat messages.
 * Supports: **bold**, *italic*, `code`, ```code blocks```, - lists, > blockquotes
 */
@Composable
fun MarkdownText(
    text: String,
    modifier: Modifier = Modifier
) {
    val blocks = parseMarkdown(text)

    Column(modifier = modifier) {
        blocks.forEach { block ->
            when (block) {
                is MarkdownBlock.CodeBlock -> {
                    CodeBlockView(block.code, block.language)
                }
                is MarkdownBlock.NormalText -> {
                    RichTextBlock(block.text)
                }
                is MarkdownBlock.BlockQuote -> {
                    BlockQuoteView(block.text)
                }
                is MarkdownBlock.ListItem -> {
                    ListItemView(block.text)
                }
            }
            Spacer(modifier = Modifier.height(4.dp))
        }
    }
}

sealed class MarkdownBlock {
    data class NormalText(val text: String) : MarkdownBlock()
    data class CodeBlock(val code: String, val language: String?) : MarkdownBlock()
    data class BlockQuote(val text: String) : MarkdownBlock()
    data class ListItem(val text: String) : MarkdownBlock()
}

private fun parseMarkdown(text: String): List<MarkdownBlock> {
    val blocks = mutableListOf<MarkdownBlock>()
    val lines = text.split("\n")
    var inCodeBlock = false
    val codeBuffer = StringBuilder()
    var codeLanguage: String? = null

    for (line in lines) {
        when {
            line.trimStart().startsWith("```") -> {
                if (inCodeBlock) {
                    blocks.add(MarkdownBlock.CodeBlock(codeBuffer.toString().trimEnd(), codeLanguage))
                    codeBuffer.clear()
                    codeLanguage = null
                    inCodeBlock = false
                } else {
                    codeLanguage = line.trimStart().removePrefix("```").trim().ifEmpty { null }
                    inCodeBlock = true
                }
            }
            inCodeBlock -> {
                codeBuffer.appendLine(line)
            }
            line.trimStart().startsWith("> ") -> {
                blocks.add(MarkdownBlock.BlockQuote(line.trimStart().removePrefix("> ")))
            }
            line.trimStart().startsWith("- ") || line.trimStart().startsWith("* ") -> {
                blocks.add(
                    MarkdownBlock.ListItem(
                        line.trimStart().removePrefix("- ").removePrefix("* ")
                    )
                )
            }
            line.isNotBlank() -> {
                blocks.add(MarkdownBlock.NormalText(line))
            }
        }
    }
    // Unclosed code block
    if (inCodeBlock && codeBuffer.isNotEmpty()) {
        blocks.add(MarkdownBlock.CodeBlock(codeBuffer.toString().trimEnd(), codeLanguage))
    }

    return blocks
}

@Composable
private fun CodeBlockView(code: String, language: String?) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(CodeBlockBg)
            .padding(12.dp)
    ) {
        Column {
            if (language != null) {
                Text(
                    text = language,
                    style = MaterialTheme.typography.labelSmall,
                    color = CodeBlockText.copy(alpha = 0.6f),
                    modifier = Modifier.padding(bottom = 4.dp)
                )
            }
            Text(
                text = code,
                style = MaterialTheme.typography.labelMedium,
                color = CodeBlockText
            )
        }
    }
}

@Composable
private fun RichTextBlock(text: String) {
    Text(
        text = buildRichText(text),
        style = MaterialTheme.typography.bodyMedium
    )
}

@Composable
private fun BlockQuoteView(text: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp)
    ) {
        Box(
            modifier = Modifier
                .width(3.dp)
                .height(24.dp)
                .clip(RoundedCornerShape(2.dp))
                .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.6f))
        )
        Spacer(modifier = Modifier.width(8.dp))
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium.copy(
                fontStyle = FontStyle.Italic,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.8f)
            )
        )
    }
}

@Composable
private fun ListItemView(text: String) {
    Row {
        Text("  •  ", style = MaterialTheme.typography.bodyMedium)
        Text(text, style = MaterialTheme.typography.bodyMedium)
    }
}

private fun buildRichText(text: String) = buildAnnotatedString {
    var remaining = text
    var isBold = false
    var isItalic = false
    var isCode = false

    while (remaining.isNotEmpty()) {
        val boldStart = if (!isCode && !isItalic) remaining.indexOf("**") else -1
        val italicStart = if (!isCode && !isBold) remaining.indexOf("*") else -1
        val codeStart = if (!isBold && !isItalic) remaining.indexOf("`") else -1

        val nextSpecial = listOf(
            boldStart to "bold",
            italicStart to "italic",
            codeStart to "code"
        ).filter { it.first >= 0 }.minByOrNull { it.first }

        if (nextSpecial == null) {
            appendStyled(remaining, isBold, isItalic, isCode)
            remaining = ""
        } else {
            val (index, type) = nextSpecial
            if (index > 0) {
                appendStyled(remaining.substring(0, index), isBold, isItalic, isCode)
            }
            remaining = when (type) {
                "bold" -> {
                    isBold = !isBold
                    remaining.substring(index + 2)
                }
                "italic" -> {
                    isItalic = !isItalic
                    remaining.substring(index + 1)
                }
                "code" -> {
                    isCode = !isCode
                    remaining.substring(index + 1)
                }
                else -> remaining
            }
        }
    }
}

private fun androidx.compose.ui.text.AnnotatedString.Builder.appendStyled(
    text: String,
    bold: Boolean,
    italic: Boolean,
    code: Boolean
) {
    val style = when {
        code -> SpanStyle(
            fontFamily = FontFamily.Monospace,
            background = CodeBlockBg.copy(alpha = 0.3f),
            fontWeight = FontWeight.Normal
        )
        bold && italic -> SpanStyle(fontWeight = FontWeight.Bold, fontStyle = FontStyle.Italic)
        bold -> SpanStyle(fontWeight = FontWeight.Bold)
        italic -> SpanStyle(fontStyle = FontStyle.Italic)
        else -> SpanStyle()
    }
    withStyle(style) {
        append(text)
    }
}
