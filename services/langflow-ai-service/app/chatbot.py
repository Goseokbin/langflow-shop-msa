from typing import List, Dict, Any
import os
import logging
import httpx
import uuid


logger = logging.getLogger(__name__)


class ShoppingAssistant:
    """Shopping mall AI assistant using Langflow"""

    def __init__(self):
        # Langflow API configuration
        self.langflow_api_key = os.getenv("LANGFLOW_API_KEY", "")
        self.langflow_url = os.getenv(
            "LANGFLOW_URL",
            "http://langflow:7860/api/v1/run/shopping-assistant"
        )

        logger.info(f"Langflow API configured: URL={self.langflow_url[:50]}...")

        self.system_prompt = """You are a helpful shopping assistant for an online shopping mall.
You can help customers with:
- Product inquiries and recommendations
- Order status and tracking
- General shopping questions
- Product availability

Be friendly, concise, and helpful. If you need specific product or order information,
indicate that you'll fetch it from the system."""

    async def chat(self, user_message: str, context: Dict = None) -> str:
        """
        Process user message and generate response using Langflow

        Args:
            user_message: User's input message
            context: Additional context (products, orders, etc.)

        Returns:
            AI assistant's response
        """
        try:
            # Prepare message with context
            full_message = user_message
            if context:
                context_str = self._format_context(context)
                full_message = f"{context_str}\n\nUser question: {user_message}"

            # Call Langflow API
            payload = {
                "output_type": "chat",
                "input_type": "chat",
                "input_value": full_message,
                "session_id": str(uuid.uuid4())
            }

            headers = {"x-api-key": self.langflow_api_key}

            async with httpx.AsyncClient(timeout=10.0) as client:

                response = await client.post(self.langflow_url, json=payload, headers=headers)
            response.raise_for_status()

            result = response.json()
            # Extract the response text from Langflow response
            if "outputs" in result and len(result["outputs"]) > 0:
                output = result["outputs"][0]
                if "outputs" in output and len(output["outputs"]) > 0:
                    return output["outputs"][0].get("results", {}).get("message", {}).get("text", "No response")

            return result.get("result", "No response from AI")

        except Exception as e:
            logger.error(f"Error in chat: {str(e)}")
            return "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."

    def _format_context(self, context: dict) -> str:
        """Format context information for the AI"""
        formatted = []

        if "products" in context:
            products = context["products"]
            formatted.append(f"Available products: {len(products)} items")
            for p in products[:5]:  # Limit to 5 products
                formatted.append(f"- {p.get('name')}: ${p.get('price')} (Stock: {p.get('inventory')})")

        if "orders" in context:
            orders = context["orders"]
            formatted.append(f"User has {len(orders)} orders")
            for o in orders[:3]:  # Limit to 3 orders
                formatted.append(f"- Order {o.get('id')}: {o.get('status')}")

        return "\n".join(formatted)

    async def analyze_intent(self, user_message: str) -> dict:
        """
        Analyze user intent to determine what action to take using Langflow

        Returns:
            dict with 'intent' and 'entities'
        """
        intent_prompt = f"""Analyze the following user message and determine the intent.
Possible intents: product_search, order_status, general_question, recommendation

User message: {user_message}

Respond with just the intent name."""

        try:
            payload = {
                "output_type": "chat",
                "input_type": "chat",
                "input_value": intent_prompt,
                "session_id": str(uuid.uuid4())
            }

            headers = {"x-api-key": self.langflow_api_key}

            async with httpx.AsyncClient(timeout=10.0) as client:

                response = await client.post(self.langflow_url, json=payload, headers=headers)
            response.raise_for_status()

            result = response.json()
            # Extract intent from response
            intent_text = "general_question"
            if "outputs" in result and len(result["outputs"]) > 0:
                output = result["outputs"][0]
                if "outputs" in output and len(output["outputs"]) > 0:
                    intent_text = output["outputs"][0].get("results", {}).get("message", {}).get("text", "general_question")

            intent = intent_text.strip().lower()

            return {
                "intent": intent,
                "original_message": user_message
            }
        except Exception as e:
            logger.error(f"Error analyzing intent: {str(e)}")
            return {
                "intent": "general_question",
                "original_message": user_message
            }

    async def generate_order_summary(
        self,
        order_id: str,
        total_amount: float,
        items: List[Dict[str, Any]],
        shipping_address: str
    ) -> str:
        """
        Generate a natural language summary of an order using Langflow API

        This workflow is instrumented for Instana GenAI monitoring using @workflow decorator

        Args:
            order_id: Order ID
            total_amount: Total order amount
            items: List of order items with product details
            shipping_address: Shipping address

        Returns:
            Natural language summary of the order
        """
        # Format items for the prompt
        items_text = []
        for item in items:
            # Handle both 'product_name' and 'name' keys for compatibility
            product_name = item.get('product_name') or item.get('name', 'Product')
            quantity = item.get('quantity', 1)
            price = item.get('price', 0)
            items_text.append(
                f"- {product_name} x {quantity} (${price} each)"
            )

        items_str = "\n".join(items_text)

        summary_prompt = f"""Generate a friendly, natural language summary of this order in English.
The summary should be conversational and include:
- A greeting and confirmation
- List of items ordered
- Total amount
- Shipping information

Order Details:
Order ID: {order_id}
Total Amount: ${total_amount:.2f}
Items:
{items_str}
Shipping Address: {shipping_address}

Generate a warm, friendly summary in 2-3 sentences."""

        # English fallback message
        fallback_summary = f"Thank you for your order! Your order #{order_id[:8]} with {len(items)} item(s) totaling ${total_amount:.2f} has been confirmed and will be shipped to {shipping_address}."

        # Try up to 2 times (initial + 1 retry)
        max_attempts = 1

        for attempt in range(max_attempts):
            try:
                # Call Langflow API for order summary generation
                payload = {
                    "output_type": "chat",
                    "input_type": "chat",
                    "input_value": summary_prompt,
                    "session_id": str(uuid.uuid4())
                }

                headers = {"x-api-key": self.langflow_api_key}

                if attempt > 0:
                    print(f"🔄 Retry attempt {attempt} for order {order_id}")
                else:
                    print(f"🚀 Calling Langflow API for order {order_id}")
                    print(f"📍 URL: {self.langflow_url}")

                logger.info(f"Calling Langflow API for order {order_id} summary (attempt {attempt + 1})")

                async with httpx.AsyncClient(timeout=10.0) as client:

                    response = await client.post(self.langflow_url, json=payload, headers=headers)
                print(f"📡 Response status: {response.status_code}")
                response.raise_for_status()

                result = response.json()
                print(f"📄 Langflow API response keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
                logger.info(f"Langflow API response: {result}")

                # Extract the summary from Langflow response - try multiple paths
                summary = None

                # Try different response structures
                if "outputs" in result and len(result["outputs"]) > 0:
                    output = result["outputs"][0]

                    # Path 1: outputs[0].outputs[0].results.message.text
                    if "outputs" in output and len(output["outputs"]) > 0:
                        inner_output = output["outputs"][0]
                        if "results" in inner_output:
                            results = inner_output["results"]
                            if isinstance(results, dict) and "message" in results:
                                message = results["message"]
                                if isinstance(message, dict) and "text" in message:
                                    summary = message["text"]
                                elif isinstance(message, str):
                                    summary = message
                            elif isinstance(results, str):
                                summary = results

                    # Path 2: outputs[0].results.message.text
                    if not summary and "results" in output:
                        results = output["results"]
                        if isinstance(results, dict) and "message" in results:
                            message = results["message"]
                            if isinstance(message, dict) and "text" in message:
                                summary = message["text"]
                            elif isinstance(message, str):
                                summary = message
                        elif isinstance(results, str):
                            summary = results

                    # Path 3: outputs[0].message or outputs[0].text
                    if not summary:
                        if "message" in output:
                            summary = output["message"] if isinstance(output["message"], str) else output["message"].get("text")
                        elif "text" in output:
                            summary = output["text"]

                if summary and isinstance(summary, str) and len(summary.strip()) > 0:
                    print(f"✅ Generated summary: {summary[:100]}...")
                    logger.info(f"Generated summary for order {order_id}: {summary}")
                    return summary.strip()
                else:
                    if attempt < max_attempts - 1:
                        print(f"⚠️  No summary found, will retry...")
                        continue
                    else:
                        print(f"⚠️  No summary after all attempts, using fallback")
                        return fallback_summary

            except Exception as e:
                print(f"❌ Error on attempt {attempt + 1}: {str(e)}")
                logger.error(f"Error generating order summary (attempt {attempt + 1}): {str(e)}")
                if attempt < max_attempts - 1:
                    print(f"🔄 Will retry...")
                    continue
                else:
                    print(f"❌ All attempts failed, using fallback")
                    import traceback
                    print(f"❌ Traceback: {traceback.format_exc()}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    return fallback_summary

        # Should not reach here, but just in case
        return fallback_summary

# Made with Bob
