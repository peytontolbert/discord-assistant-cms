import re
import json
import time
def locate_element(browser, text_agent, element_name):
    browser.take_screenshot("images/locate_element.png")
    result = text_agent.chat(input={
        "query": f"Semantically describe the '{element_name}' and spatial location in the image.",
        "image": "images/locate_element.png"
    })
    print(result)
    return result

def locate_element_coordinates(browser, qwen2vl, element_name):
    """Ask the TextAgent to locate the precise coordinates of an element."""
    browser.take_screenshot("images/element_screenshot.png")
    result = qwen2vl.chat(input={
        "query": f"Please locate the center coordinates of:\n{element_name}\n reply with the exact coordinates as (x: , y: ) ",
        "image": "images/element_screenshot.png"
    })
    x, y = parse_coordinates(result)
    print(f"Located coordinates for '{element_name}': ({x}, {y})")
    return x, y

def parse_coordinates(browser, result):
    """Parse the x and y coordinates from the TextAgent result."""
    # Ensure result is a string
    if isinstance(result, list):
        result = ' '.join(result)
    elif not isinstance(result, str):
        print(f"Unexpected result type: {type(result)}")
        return None, None

    # Define regex patterns for different coordinate formats
    patterns = [
        r'\(x:\s*(\d+),\s*y:\s*(\d+)\)',  # Pattern: (x: 488, y: 552)
        r'\((\d+),\s*(\d+)\)'              # Pattern: (488, 552)
    ]

    for pattern in patterns:
        match = re.search(pattern, result)
        if match:
            # Get coordinates in screenshot space (1000x1000)
            screenshot_x, screenshot_y = map(int, match.groups())
            
            # Convert screenshot coordinates (1000x1000) to viewport coordinates
            viewport_x, viewport_y = browser.normalize_coordinates(
                screenshot_x, 
                screenshot_y, 
                from_screenshot=True
            )
            
            print(f"Converting coordinates: Screenshot ({screenshot_x}, {screenshot_y}) -> Viewport ({viewport_x}, {viewport_y})")
            return int(screenshot_x), int(screenshot_y)

    print("No valid coordinates found in the result.")
    return None, None


def refine_position_with_history(browser, qwen2vl, movement_history, element_name):
    """Refine position with coordinate normalization."""
    for attempt in range(5):
        last_position = movement_history[-1] if movement_history else None
        prompt_history = "Movement history:\n" + "\n".join(
            [f"Move {i+1}: (x: {pos['x']}, y: {pos['y']}) - Info: {pos['more_info']}" for i, pos in enumerate(movement_history)]
        )
        
        # Convert viewport coordinates to screenshot coordinates for the filename
        if last_position:
            screenshot_x, screenshot_y = browser.normalize_coordinates(
                last_position['x'], 
                last_position['y'], 
                from_screenshot=False
            )
            zoom_filename = f"images/refine_position_{int(screenshot_x)}_{int(screenshot_y)}.png"
        else:
            zoom_filename = "images/refine_position.png"
        
        browser.take_screenshot(zoom_filename)
        
        result = qwen2vl.chat(input={
            "query": f"""
You are a mouse controller GPT. Analyze the mouse movement history to refine positioning over the '{element_name}' link. 
Consider each previous move and the accompanying information. 
Provide the response in JSON format with "coordinates" and "more_info".

Example:
{{"coordinates": {{"x": 400, "y": 300}}, "more_info": "Adjusted position based on previous left offset."}}

{prompt_history}
            """,
            "image": zoom_filename
        })

        # Parse the new suggested coordinates from JSON
        try:
            # Handle both list and string results
            if isinstance(result, list):
                result_str = result[0]
            else:
                result_str = result
                
            # Clean up the JSON string
            result_str = result_str.replace('{{{', '{').replace('}}}', '}').strip('[]\'\"')
            
            # Try to extract coordinates using regex if JSON parsing fails
            try:
                data = json.loads(result_str)
            except json.JSONDecodeError:
                # Fallback to regex pattern matching
                coord_pattern = r'"x":\s*(\d+),\s*"y":\s*(\d+)'
                match = re.search(coord_pattern, result_str)
                if match:
                    screenshot_x, screenshot_y = map(int, match.groups())
                    data = {
                        "coordinates": {"x": screenshot_x, "y": screenshot_y},
                        "more_info": "Extracted via regex"
                    }
                else:
                    raise ValueError("Could not extract coordinates")

            # Coordinates from VL model are in screenshot space (1000x1000)
            screenshot_x = int(data["coordinates"]["x"])
            screenshot_y = int(data["coordinates"]["y"])
            # Convert to viewport coordinates
            new_x, new_y = browser.normalize_coordinates(screenshot_x, screenshot_y, from_screenshot=True)
            more_info = data.get("more_info", "")
            
            print(f"Successfully parsed coordinates: ({new_x}, {new_y})")
            
        except (ValueError, KeyError) as e:
            print(f"Refinement step failed: Could not extract coordinates. Error: {e}")
            print(f"Raw result: {result}")
            break

        # Update movement history and move the mouse
        movement_history.append({"x": new_x, "y": new_y, "more_info": more_info})
        browser.move_mouse_to(new_x, new_y)

        # Verify the new position
        confidence = verify_mouse_position(new_x, new_y, element_name)
        if confidence >= 90:  # Threshold can be adjusted as needed
            print(f"Position refined and verified at ({new_x}, {new_y}) with confidence {confidence}.")
            return new_x, new_y, movement_history  # Return refined and verified coordinates

    print("Could not verify position after multiple refinements.")
    return None, None, movement_history  # Return None if no position verifies after refinements


def verify_mouse_position(browser, qwen2vl, movement_history, viewport_x, viewport_y, element_name):
    """Verify mouse position with coordinate normalization."""
    browser.move_mouse_to(viewport_x, viewport_y)
    
    # Convert viewport coordinates back to screenshot coordinates for the filename
    #screenshot_x, screenshot_y = self.browser.normalize_coordinates(
    #    viewport_x, 
    #    viewport_y, 
    #    from_screenshot=False
    #)
    
    filename = f"images/mouse_position_{int(viewport_x)}_{int(viewport_y)}.png"
    browser.take_screenshot(filename)
    
    result = qwen2vl.chat(input={
        "query": f"""
Is '{element_name}' precisely highlighted with the red circle? Locate the red circle and ensure it is centered on {element_name}.
Reply with a JSON object containing:
- "confidence": a score between 0 and 100,
- "more_info": additional information about the verification.
Example:
{{"confidence": 85, "more_info": "Mouse is slightly to the left of the target."}}
        """,
        "image": filename
    })
    print(f"Verification result: {result}")
    try:
        # Updated parsing to handle list objects
        if isinstance(result, list) and len(result) > 0:
            data = json.loads(result[0].strip())
        elif isinstance(result, str):
            data = json.loads(result.strip())
        else:
            print(f"Unexpected result format: {result}")
            data = {}
        
        confidence = float(data.get("confidence", 0.0))
        more_info = data.get("more_info", "")
        # Include more_info in movement history for clearer instructions
        movement_history.append({"x": viewport_x, "y": viewport_y, "more_info": more_info})
    except (ValueError, json.JSONDecodeError):
        confidence = 0.0  # Default to 0 if parsing fails
        more_info = "Invalid response format."
        movement_history.append({"x": viewport_x, "y": viewport_y, "more_info": more_info})
    return confidence, movement_history


def click_element(browser, qwen2vl, movement_history, element_name):
    # Step 1: Directly locate the element's coordinates
    x, y = locate_element_coordinates(browser, qwen2vl, element_name)
    if x is None or y is None:
        print(f"Could not locate '{element_name}' coordinates. Exiting.")
        return

    # Add the initial position to movement history
    movement_history.append({"x": x, "y": y, "more_info": ""})

    # Step 2: Move to the located coordinates and verify
    confidence, movement_history = verify_mouse_position(browser, qwen2vl, movement_history, x, y, element_name)
    if confidence >= 90:  # Threshold can be adjusted as needed
        new_x, new_y = browser.normalize_coordinates(x,y,from_screenshot=True)
        browser.click_at(x, y)
        browser.take_screenshot(f"images/{element_name}_clicked_{x}_{y}.png")
        print(f"Successfully clicked on '{element_name}' at ({x}, {y}) with confidence {confidence}.")
    else:
        # Step 3: If confidence is low, refine the position incrementally
        print(f"Initial verification confidence ({confidence}) insufficient for '{element_name}' at ({x}, {y}). Refining position.")
        refined_x, refined_y, movement_history = refine_position_with_history(browser, qwen2vl, movement_history, element_name)

        if refined_x is not None and refined_y is not None:
            browser.click_at(refined_x, refined_y)
            browser.take_screenshot(f"images/{element_name}_clicked_{refined_x}_{refined_y}.png")
            print(f"Successfully clicked on '{element_name}' after refinement at ({refined_x}, {refined_y}).")
        else:
            print(f"Could not verify and refine position for '{element_name}'. Exiting.")


def move_to_element(browser, qwen2vl, movement_history, element_name):

    # Step 1: Directly locate the element's coordinates
    x, y = locate_element_coordinates(browser, qwen2vl, element_name)
    if x is None or y is None:
        print(f"Could not locate '{element_name}' coordinates. Exiting.")
        return

    # Add the initial position to movement history
    movement_history.append({"x": x, "y": y, "more_info": ""})

    # Step 2: Move to the located coordinates and verify
    confidence, movement_history = verify_mouse_position(browser, qwen2vl, movement_history, x, y, element_name)
    if confidence >= 90:  # Threshold can be adjusted as needed
        browser.click_at(x, y)
        browser.take_screenshot(f"images/{element_name}_clicked_{x}_{y}.png")
        print(f"Successfully clicked on '{element_name}' at ({x}, {y}) with confidence {confidence}.")
    else:
        # Step 3: If confidence is low, refine the position incrementally
        print(f"Initial verification confidence ({confidence}) insufficient for '{element_name}' at ({x}, {y}). Refining position.")
        refined_x, refined_y, movement_history = refine_position_with_history(browser, qwen2vl, movement_history, element_name)

        if refined_x is not None and refined_y is not None:
            browser.move_mouse_to(refined_x, refined_y)
            browser.take_screenshot(f"images/{element_name}_clicked_{refined_x}_{refined_y}.png")
            print(f"Successfully clicked on '{element_name}' after refinement at ({refined_x}, {refined_y}).")
        else:
            print(f"Could not verify and refine position for '{element_name}'. Exiting.")


def click_and_type_element(browser, qwen2vl, movement_history, element_name, text_to_type):
    """Click an element and type text into it."""
    
    # Locate and click the element
    x, y = locate_element_coordinates(browser, qwen2vl, element_name)
    if x is None or y is None:
        print(f"Could not locate '{element_name}' coordinates. Exiting.")
        return False

    # Add the initial position to movement history
    movement_history.append({"x": x, "y": y, "more_info": ""})

    # Move to coordinates and verify
    confidence, movement_history = verify_mouse_position(browser, qwen2vl, movement_history, x, y, element_name)
    if confidence >= 90:
        browser.click_and_type(x, y, text_to_type)
        browser.take_screenshot(f"images/{element_name}_typed_{x}_{y}.png")
        print(f"Successfully clicked and typed into '{element_name}' at ({x}, {y})")
        return True
    else:
        # Refine position if needed
        refined_x, refined_y, movement_history = refine_position_with_history(browser, qwen2vl, movement_history, element_name)
        if refined_x is not None and refined_y is not None:
            browser.click_and_type(refined_x, refined_y, text_to_type)
            browser.take_screenshot(f"images/{element_name}_typed_{refined_x}_{refined_y}.png")
            print(f"Successfully clicked and typed after refinement at ({refined_x}, {refined_y})")
            return True
        else:
            print(f"Could not verify and refine position for '{element_name}'. Exiting.")
            return False


def configure_audio_devices(browser, qwen2vl, movement_history):
    """Configure Discord to use VB-Audio Cable for audio devices."""
    # Click user settings
    click_element(browser, qwen2vl, movement_history, "User Settings")
    time.sleep(1)
    
    # Click Voice & Video settings
    click_element(browser, qwen2vl, movement_history, "Voice & Video")
    time.sleep(1)
    
    # Configure input device (VB-Audio Cable)
    click_element(browser, qwen2vl, movement_history, "Input Device dropdown")
    time.sleep(0.5)
    click_element(browser, qwen2vl, movement_history, "CABLE Output (VB-Audio Virtual Cable)")
    
    # Configure output device
    click_element(browser, qwen2vl, movement_history, "Output Device dropdown")
    time.sleep(0.5)
    click_element(browser, qwen2vl, movement_history, "Speakers")  # Or your preferred output device
    
    # Close settings
    click_element(browser, qwen2vl, movement_history, "ESC")
    time.sleep(1)
